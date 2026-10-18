#!/usr/bin/env python3
"""Q3-V2-R1: read-only analysis of persisted schedules; NEVER schedules jobs.

Run from the repository root. Relative input paths are recorded for authorized
local access; a source hash does not make an ignored artifact remotely available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd

PROBLEM = Path('problems/2026_gpu_scheduling')
V1 = Path('results/20261015-b-q3-fixed-split-c9e8f1a2')
S2 = Path('results/20261015-b-q3-s2-fixed-split-v1')
V2 = Path('results/20261017-b-q3-v2-shape-a17c4e9d')
H = 7_776_000
TARGET = 'A100-SXM4-80GB'
POLICIES = ('FCFS', 'SJF-HOL')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def checked(frame):
    require(frame.index.is_unique and not frame.index.hasnans, 'duplicate/missing IDs')
    require(len(frame) > 0, 'empty fixed cohort')
    require(np.isfinite(frame[['start', 'finish', 'submit_time']].to_numpy()).all(), 'missing/nonfinite timing')
    return frame.sort_index()


def pair(candidate, reference):
    """Signed candidate minus reference, using the SAME full original-ID cohort."""
    a, b = checked(candidate), checked(reference)
    require(a.index.equals(b.index), 'paired original ID mismatch')
    require(a.submit_time.equals(b.submit_time), 'paired submission mismatch')
    delta = a.finish - b.finish
    wait_delta = a.start - b.start
    harmed = delta[delta > 0]
    wait_harmed = wait_delta[wait_delta > 0]
    return {
        'n': len(a),
        'mean_finish_delta_hours': float(delta.mean() / 3600),
        'harmed_jobs': len(harmed), 'improved_jobs': int((delta < 0).sum()),
        'equal_jobs': int((delta == 0).sum()),
        'positive_finish_delay_job_hours': float(harmed.sum() / 3600),
        'harmed_mean_finish_delta_hours': float(harmed.mean() / 3600) if len(harmed) else None,
        'harmed_p99_finish_delta_hours': float(harmed.quantile(.99) / 3600) if len(harmed) else None,
        'p99_finish_delta_hours': float(delta.quantile(.99) / 3600),
        'max_finish_delta_hours': float(delta.max() / 3600),
        'mean_wait_delta_hours': float(wait_delta.mean() / 3600),
        'wait_harmed_jobs': len(wait_harmed),
        'positive_wait_delay_job_hours': float(wait_harmed.sum() / 3600),
        'wait_harmed_mean_delta_hours': float(wait_harmed.mean() / 3600) if len(wait_harmed) else None,
        'p99_wait_delta_hours': float(wait_delta.quantile(.99) / 3600),
        'max_wait_delta_hours': float(wait_delta.max() / 3600),
        'reference_zero_wait_n': int(b.start.eq(b.submit_time).sum()),
        'reference_zero_wait_newly_delayed': int((b.start.eq(b.submit_time) & a.start.gt(a.submit_time)).sum()),
    }


def metrics(frame):
    wait = frame.start - frame.submit_time
    jct = frame.finish - frame.submit_time
    return {
        'jobs': len(frame), 'completed_at_horizon': int(frame.finish.le(H).sum()),
        'mean_wait_hours': float(wait.mean() / 3600),
        'mean_jct_hours': float(jct.mean() / 3600),
        'mean_relative_completion_delay_hours': float((jct - frame.original_duration).mean() / 3600),
        'p95_wait_hours': float(wait.quantile(.95) / 3600),
        'p99_wait_hours': float(wait.quantile(.99) / 3600),
        'max_wait_hours': float(wait.max() / 3600),
    }


def discrete_worst(rows):
    """Post-hoc two-point maximum per FIXED option and policy; not an interval bound."""
    out = []
    for policy in sorted({r['policy'] for r in rows}):
        block = []
        for option in ('M0', 'R0', 'R-shape'):
            selected = [r for r in rows if r['cohort'] == 'A10' and r['policy'] == policy and r['option'] == option]
            values = {r['sigma']: r['mean_jct_hours'] for r in selected}
            require(len(selected) == len(values), 'duplicate discrete scenario')
            require(set(values) == ({None} if option == 'M0' else {1, 2}), 'missing/extra discrete scenario')
            a, b = (values[None], values[None]) if option == 'M0' else (values[1], values[2])
            block.append({'policy': policy, 'option': option, 'cohort': 'A10',
                          'sigma1_mean_jct_hours': a, 'sigma2_mean_jct_hours': b,
                          'worst_mean_jct_hours': max(a, b), 'post_hoc': True})
        best = min(r['worst_mean_jct_hours'] for r in block)
        for r in block:
            r['best_of_three'] = r['worst_mean_jct_hours'] == best
        out.extend(block)
    return out


def route_sets(raw, nodes):
    """Independent arithmetic/hash audit, NOT a call to the production router."""
    donors = nodes[nodes.gpu_model.eq(TARGET)].sort_values('node_name').head(60)
    require(len(donors) == 60 and donors.cpu_num.eq(128).all()
            and donors.gpu_capacity_num.eq(8).all(), 'donor shape changed')
    require(int(nodes.gpu_model.eq(TARGET).sum()) == 432, 'native partition size')
    r0 = []
    for row in raw[raw.gpu_model.eq('A10')].itertuples():
        cpu_units = round(float(row.cpu_request) * 100)
        slots = 8 // int(row.gpu_request)
        if cpu_units > 0:
            slots = min(slots, 12800 // cpu_units)
        eligible = 60 * slots >= row.worker_num
        hashed = int.from_bytes(hashlib.sha256(f'q3-fixed-split-v1:{int(row.Index)}'.encode()).digest(), 'big')
        if eligible and 10 * hashed < 2**256:
            r0.append(row.Index)
    r0 = pd.Index(r0, name='job_name').sort_values()
    shape = raw.loc[r0]
    shape = shape[shape.cpu_request.le(16 * shape.gpu_request)].index
    return r0, shape, donors


def distribution(series):
    return {'n': len(series), 'mean': float(series.mean()), 'min': float(series.min()),
            'p50': float(series.quantile(.5)), 'p95': float(series.quantile(.95)),
            'p99': float(series.quantile(.99)), 'max': float(series.max())}


def route_audit(raw, r0, shape):
    excluded = r0.difference(shape)
    require(shape.isin(r0).all() and len(excluded) == 605, 'R-shape subset/count mismatch')
    a10 = raw[raw.gpu_model.eq('A10')]
    def work(f, resource):
        return float((f.duration * f.worker_num * f[resource]).sum())
    out = {'shape_limit_cpu_per_gpu': 16, 'subset_verified': True,
           'sigma_and_policy_selected_ids_invariant': True,
           'excluded_n': len(excluded), 'r0_n': len(r0), 'retained_n': len(shape),
           'excluded_fraction_of_r0_jobs': len(excluded) / len(r0),
           'units': 'original work: GPU-seconds / vCPU-seconds; original duration: seconds; gang: workers',
           'groups': {}}
    for name, ids in [('R0', r0), ('retained_Rshape', shape), ('excluded_R0_minus_Rshape', excluded)]:
        sub = raw.loc[ids]
        entry = {'n': len(sub), 'id_sha256': hashlib.sha256(''.join(f'{i}\n' for i in sorted(ids)).encode()).hexdigest(),
                 'duration_seconds': distribution(sub.duration),
                 'gang_workers': distribution(sub.worker_num),
                 'gang_counts': {str(k): int(v) for k, v in sub.worker_num.value_counts().sort_index().items()},
                 'cpu_per_gpu': distribution(sub.cpu_request / sub.gpu_request)}
        for resource, label in [('gpu_request', 'gpu'), ('cpu_request', 'cpu')]:
            value = work(sub, resource)
            entry[label + '_work'] = {'original_seconds': value,
                'r0_original_seconds_denominator': work(raw.loc[r0], resource),
                'fraction_of_r0_original': value / work(raw.loc[r0], resource),
                'all_A10_original_seconds_denominator': work(a10, resource),
                'fraction_of_all_A10_original': value / work(a10, resource),
                'effective_seconds_if_routed_sigma1': value,
                'effective_seconds_if_routed_sigma2': 2 * value}
        out['groups'][name] = entry
    out['effective_work_note'] = 'Excluded jobs execute natively at original work under R-shape; their doubled work is only applicable when routed by R0 sigma2.'
    return out


def paths(policy, option, sigma):
    if option == 'M0' or (option == 'R0' and sigma == 1):
        label = 'M0' if option == 'M0' else 'M1'
        base = Path('outputs/b-q3-fixed-split-v1-final')
        return base / f'{policy}_{label}_jobs.csv.gz', base / f'{policy}_{label}_placements.csv.gz'
    base = (Path('outputs/q3-v2-r0-sigma2') / f'S5_{policy}' if option == 'R0'
            else Path('outputs/q3-v2-shape-a17c4e9d') / f'Rshape_sigma{sigma}_{policy}')
    return base / 'jobs.csv.gz', base / 'placements.csv.gz'


def markdown_table(rows, columns):
    def fmt(v):
        if v is None:
            return 'N/A'
        return f'{v:.6f}' if isinstance(v, float) else str(v)
    return '\n'.join(['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join('---' for _ in columns) + ' |'] +
                     ['| ' + ' | '.join(fmt(r[c]) for c in columns) + ' |' for r in rows])


def publish(out, rows, pairs, worst, routing):
    # Both languages and all tables are generated from these same records.
    tables = []
    for policy in POLICIES:
        for cohort in ('A10', 'ALL'):
            block = [r for r in rows if r['policy'] == policy and r['cohort'] == cohort]
            tables += [f'### {policy}, {cohort} (n={block[0]["jobs"]})\n', markdown_table(block, [
                'option', 'sigma', 'mean_wait_hours', 'mean_jct_hours', 'completed_at_horizon',
                'vs_M0_mean_finish_delta_hours', 'vs_R0_mean_finish_delta_hours',
                'vs_M0_harmed_jobs', 'vs_R0_harmed_jobs',
                'vs_M0_positive_finish_delay_job_hours', 'vs_R0_positive_finish_delay_job_hours',
                'p95_wait_hours', 'p99_wait_hours', 'max_wait_hours',
                'native_mean_wait_delta_vs_M0_hours', 'native_invariant_vs_R0']), '']
    (out / 'main_table.md').write_text('# Complete fixed-cohort comparison / 固定原始群體主表\n\n'
        'Hours unless count or job-hours is specified. Negative finish delta is earlier. '
        'M0 is one shared no-substitution schedule per policy (sigma N/A); its two direct R0 reverse comparisons '
        'are in paired.csv, not filled with zeros here. Native invariance means both timing and placement against '
        'the same-sigma 60-node partition. M0 has 432 native nodes, so this partition comparison is N/A.\n\n'
        + '\n'.join(tables))
    (out / 'discrete_worst.md').write_text('# Post-hoc discrete maxima / 事後離散最大值\n\n' + markdown_table(worst, [
        'policy', 'option', 'sigma1_mean_jct_hours', 'sigma2_mean_jct_hours', 'worst_mean_jct_hours', 'best_of_three']) + '\n')
    text = ['# Q3-V2-R1 supplement / 補充說明\n',
        '[Complete main table / 完整主表](main_table.md) · [Discrete maxima / 離散最大值](discrete_worst.md) · '
        '[Paired evidence](paired.csv) · [Routing/work](routing.json) · [Sources and access](manifest.json)\n',
        '## Protocol / 比較口徑\n',
        'M0: no substitution. R0: V1 eligibility and 10% SHA256, namespace `q3-fixed-split-v1`, 60 dedicated A100 nodes. '
        'R-shape: the same rule plus ≤16 vCPU/GPU. Native A100 uses the other 372 nodes. '
        'Fixed original cohorts: A10 n=111284 (routed and unrouted), ALL n=224112, native A100 n=80877. '
        'H=7776000 seconds; completed means finish≤H; waiting/JCT use complete drain. Sigma 1 and 2 are assumptions, not hardware measurements.\n',
        'M0 不替代；R0 為 V1 eligibility、同命名空間 10% hash 與 60 台專區；R-shape 再加正式 16 vCPU/GPU 條件。'
        '固定原始群體包含分流與未分流作業；完成數用 90 天窗口，等待與 JCT 用完整排空。兩個 sigma 均為情景假設。\n',
        'All paired deltas are candidate minus named reference over identical original IDs. Positive totals sum only positive per-ID deltas; '
        'harmed means use harmed n, and n=0 gives null/N/A. Unprefixed quantiles use the full named cohort; '
        '`harmed_` quantiles use only finish-delta>0. `wait_harmed_` uses start-delta>0. '
        'All quantiles use linear interpolation, independently in each direction.\n',
        '配對差為候選減去指定基線；受損條件均值用受損人數，n=0 為 null。全群體分位數與受損子群分位數分開；'
        '零等待新增延遲以該列 reference 的原零等待作業為分母。M0 與同 sigma R0 不能互換。\n',
        '## Observed tradeoffs / 已觀察取捨\n']
    for policy in POLICIES:
        get = lambda option, sigma: next(r for r in rows if r['policy'] == policy and r['cohort'] == 'A10'
                                        and r['option'] == option and r['sigma'] == sigma)
        m0 = get('M0', None)
        for sigma in (1, 2):
            a, b = get('R-shape', sigma), get('R0', sigma)
            p = next(x for x in pairs if x['policy'] == policy and x['cohort'] == 'A10'
                     and x['option'] == 'R-shape' and x['sigma'] == sigma and x['reference'] == 'R0')
            text.append(f'{policy}, sigma={sigma}: A10 mean JCT M0/R0/R-shape = '
                f'{m0["mean_jct_hours"]:.6f}/{b["mean_jct_hours"]:.6f}/{a["mean_jct_hours"]:.6f} h. '
                f'R-shape vs R0: {p["mean_finish_delta_hours"]:+.6f} h; {p["harmed_jobs"]} finish later, '
                f'positive delay {p["positive_finish_delay_job_hours"]:.6f} job-h; '
                f'vs M0: {a["vs_M0_mean_finish_delta_hours"]:+.6f} h and {a["vs_M0_harmed_jobs"]} finish later.\n')
            text.append(f'繁中：{policy}、sigma={sigma}，上述同群體三方案 JCT 及兩個基線分開比較；'
                f'相對 R0 有 {p["harmed_jobs"]} 個較晚完成，正延遲合計 {p["positive_finish_delay_job_hours"]:.6f} 作業小時，'
                f'相對 M0 較晚完成者為 {a["vs_M0_harmed_jobs"]}，不能把平均改善解讀為人人受益。\n')
    text += ['## Post-hoc decision / 事後決策\n',
        'For each fixed policy and option, F is original-A10 mean JCT and F_worst=max{F(1),F(2)}. '
        'R0 has lower mean JCT at sigma=1 in both policies; R-shape has the smallest two-point maximum among the three options in both policies. '
        'A choice stays fixed across the two scenarios; policies are never spliced. '
        'For conditions near the tested sigma=1, R0 can be preferable for average efficiency, but no neighborhood of superiority is proven.\n',
        '每個固定政策及方案的 F 為原始 A10 平均 JCT；F_worst 為兩個已測點的最大值。兩政策在 sigma=1 都由 R0 有較佳平均效率，'
        'R-shape 則在三個選項中具有較小離散最大值，可作保守選項；不能每次事後知道 sigma 再換贏家，也不能跨政策拼接。'
        '接近 sigma=1 時偏重效率可考慮 R0，但未證明任何鄰域優勢。\n',
        'This is post-hoc analysis, not a pre-frozen selection criterion, an upper bound on sigma∈[1,2], '
        'a guarantee at unknown true speed, or a global robust-optimization solution. No monotonicity is proven. '
        'There are no probabilities (including 50/50), interpolation, root finding, or precise/unique sigma*.\n',
        '此為事後離散情景分析，不是事前凍結選點、區間上界、真實未知速度保證或全域 robust optimization。'
        '未證明單調性，端點不保證涵蓋區間最壞值；不假定概率、不插值、不求根或精確／唯一臨界倍率。\n',
        '## Selection/work / 篩選與工作量\n']
    e = routing['groups']['excluded_R0_minus_Rshape']
    text += [f'Excluded {routing["excluded_n"]}/{routing["r0_n"]} jobs '
        f'({100*routing["excluded_fraction_of_r0_jobs"]:.6f}%); retained {routing["retained_n"]}. '
        f'Excluded original GPU-work {e["gpu_work"]["original_seconds"]:.0f} GPU-s '
        f'({100*e["gpu_work"]["fraction_of_r0_original"]:.6f}% of R0 selected GPU-work); '
        f'CPU-work {e["cpu_work"]["original_seconds"]:.0f} vCPU-s '
        f'({100*e["cpu_work"]["fraction_of_r0_original"]:.6f}% of R0 selected CPU-work).\n',
        f'繁中：排除 {routing["excluded_n"]} 個，占 R0 轉移數 {100*routing["excluded_fraction_of_r0_jobs"]:.6f}%；'
        f'卻占 R0 原始 GPU-work {100*e["gpu_work"]["fraction_of_r0_original"]:.6f}%、'
        f'CPU-work {100*e["cpu_work"]["fraction_of_r0_original"]:.6f}%。\n',
        'Routing sets are identical across the two sigmas and policies; shape changes both resource composition and selected load. '
        'Original work uses original duration and worker requirements. Effective routed sigma2 work is twice original work; excluded jobs remain native under R-shape. '
        'No experiment identifies a pure CPU-ratio, duration or load causal contribution; matched controls would require additional experiments outside this task.\n',
        '兩倍率與政策的選中集合相同；少量排除者占較大工作量，形狀與負載同時改變。原始工作量與替代後工作量分開。'
        '未識別 CPU 比例、時長或負載的單一因果效果；區分機制需額外實驗，本輪不執行。\n',
        '## Adoption and evidence limits / 採納範圍與限制\n',
        'Retain R0 and R-shape as explicit alternatives, including the sigma1 disadvantage; do not make R-shape an unconditional default. '
        'Candidate B remains IMPLEMENTATION_DEFERRED. No new schedules, sigma values, controls or candidates. '
        'Native A100 timing and placement match same-sigma R0 exactly; zero extra waiting vs M0 is an observation on this trace, not a future-trace guarantee. '
        'Existing physical replay PASS is cited with hashes; physical replay is not rerun in R1. '
        'Full timing/placement archives remain LOCAL_ONLY; cross-machine delivery BLOCKED. No PDF or V1 paper is changed.\n',
        '保留 R0／R-shape 兩個明確選項與 sigma1 負面結果，不改無條件預設。B 延後、零新排程。'
        '原生 A100 對同分區 R0 的逐 ID timing／placement 完全一致；對 M0 零額外等待僅為此 trace 觀察。'
        '沿用有雜湊的既有物理 replay，R1 未重跑。大帳本仍 LOCAL_ONLY／跨機 BLOCKED；不更動 V1 論文或 PDF。\n',
        'AI use: Codex generated the postprocessor, regression tests and bilingual supplement; human review remains pending.\n']
    distributions = []
    for name in ('retained_Rshape', 'excluded_R0_minus_Rshape'):
        group = routing['groups'][name]
        for measure in ('duration_seconds', 'gang_workers', 'cpu_per_gpu'):
            distributions.append({'group': name, 'measure': measure, **group[measure]})
    text += ['## Retained/excluded distributions / 保留與排除分布\n',
             markdown_table(distributions, ['group', 'measure', 'n', 'mean', 'min', 'p50', 'p95', 'p99', 'max']),
             '\nOriginal-duration/worker distributions; quantiles use each named routed-set subgroup, not all A10. '
             'Work denominators and sigma-scaled work are in routing.json. / 此處分母為指定保留或排除子群，非全部 A10。\n',
             '## Reproduction / 重現\n',
             'Python/pandas/numpy versions and every input SHA256 are in manifest.json. '
             'Use the existing Problem B environment; obtain authorized local evidence at the listed relative paths first. '
             'This command reads saved timing only and requires a new output directory.\n',
             '```bash\npython problems/2026_gpu_scheduling/experiments/analyze_q3_v2_tradeoffs.py '
             '--out results/<new-unused-revision-id>\n```\n',
             'Physical replay and old scheduling suites are not executed by this command. '
             'Small result tables alone do not replace the unavailable cross-machine ledgers. / '
             '先取得獲授權帳本；此命令僅後處理，不能把摘要表當成跨機帳本已交付。\n']
    (out / 'README.md').write_text('\n'.join(text))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'use a new revision output directory')
    source = {}
    def record(path, expected=None):
        path = Path(path)
        sha = digest(path)
        if expected is not None:
            require(sha == expected, f'source hash mismatch: {path}')
        source[str(path)] = {'sha256': sha, 'bytes': path.stat().st_size}
        return path
    def read_json(path):
        return json.loads(record(path).read_text())
    manifest = read_json(V2 / 'manifest.json')
    for path, expected in manifest['results_sha256'].items():
        record(path, expected)
    v1_run = read_json(V1 / 'run.json')
    v1_metrics = read_json(V1 / 'metrics.json')
    for path in [V1 / 'verified.json', S2 / 'manifest.json', S2 / 'independent_verification.json',
                 PROBLEM / 'paper/output/integration_runtime_equivalence.json']:
        record(path)
    raw_path = PROBLEM / 'data/raw/job_info_clean.csv'
    node_path = PROBLEM / 'data/raw/node_info_df.csv'
    for path in (raw_path, node_path):
        record(path, manifest['data_sha256'][path.name])
    raw = pd.read_csv(raw_path).set_index('job_name').sort_index()
    nodes = pd.read_csv(node_path)
    require(raw.index.is_unique and len(raw) == 224112, 'raw fixed population')
    r0, shape, donors = route_sets(raw, nodes)
    routing = route_audit(raw, r0, shape)
    masks = {'A10': raw.gpu_model.eq('A10'), 'ALL': np.ones(len(raw), dtype=bool),
             'native_A100': raw.gpu_model.eq(TARGET)}
    archive = record(manifest['delivery']['path'], manifest['delivery']['sha256'])
    require(archive.stat().st_size == manifest['delivery']['bytes'], 'archive size')
    rows, pairs, native, checks = [], [], [], []
    zip_source = zipfile.ZipFile(archive)
    for policy in POLICIES:
        frames, ledgers = {}, {}
        cases = [('M0', None), ('R0', 1), ('R0', 2), ('R-shape', 1), ('R-shape', 2)]
        for option, sigma in cases:
            jp, lp = paths(policy, option, sigma)
            for path in (jp, lp):
                expected = None
                if option == 'M0' or (option == 'R0' and sigma == 1):
                    expected = v1_run['outputs'][path.name]
                elif option == 'R0':
                    expected = manifest['r0_reference']['sigma2']['source_schedule_sha256'][policy][
                        'jobs' if path == jp else 'placements']
                else:
                    expected = hashlib.sha256(zip_source.read(str(path))).hexdigest()
                record(path, expected)
            f = checked(pd.read_csv(jp).set_index('job_name'))
            require(f.index.equals(raw.index), 'raw timing ID set')
            for col in ['gpu_model', 'duration', 'cpu_request', 'gpu_request', 'worker_num', 'submit_time']:
                saved_col = {'gpu_model': 'original_gpu_model', 'duration': 'original_duration'}.get(col, col)
                require(np.array_equal(f[saved_col].to_numpy(), raw[col].to_numpy()), 'raw attribute: ' + col)
            routed = f.index[f.route_reason.eq('routed')]
            expect = raw.index[:0] if option == 'M0' else r0 if option == 'R0' else shape
            require(routed.equals(expect), 'independent route ID mismatch')
            effective = raw.duration.copy()
            if len(expect):
                effective.loc[expect] *= sigma
            require(f.duration.equals(effective), 'effective duration mismatch')
            require(f.finish.eq(f.start + f.duration).all() and f.start.ge(f.submit_time).all(), 'timing identity')
            ledger = pd.read_csv(lp).sort_values(['job_name', 'node_name']).reset_index(drop=True)
            require(not ledger.duplicated(['job_name', 'node_name']).any(), 'duplicate placement rows')
            require(set(ledger.job_name) == set(raw.index), 'placement job IDs')
            counts = ledger.groupby('job_name').workers.sum().sort_index()
            require(counts.equals(raw.worker_num), 'placement gang count')
            require(ledger.node_name.isin(nodes.node_name).all() and ledger.workers.gt(0).all(), 'placement values')
            frames[option, sigma] = f
            native_ids = raw.index[masks['native_A100']]
            ledgers[option, sigma] = ledger[ledger.job_name.isin(native_ids)].reset_index(drop=True)
            if option == 'M0' or (option == 'R0' and sigma == 1):
                official = v1_metrics[policy]['M0' if option == 'M0' else 'M1']['cohorts']
            else:
                official = read_json((S2 / f'S5_{policy}_metrics.json') if option == 'R0'
                                     else V2 / f'Rshape_sigma{sigma}_{policy}_metrics.json')
            for cohort, mask in masks.items():
                m = metrics(f[mask])
                old = official['original_A10' if cohort == 'A10' and 'original_A10' in official else cohort]
                for key, value in m.items():
                    if key == 'mean_relative_completion_delay_hours' and key not in old:
                        continue  # V1 did not publish this field; it is computed from timing above.
                    require(np.isclose(value, old[key], rtol=1e-11, atol=1e-9), f'published metric mismatch {policy}/{option}/{key}')
                rows.append({'policy': policy, 'option': option, 'sigma': sigma, 'cohort': cohort, **m})
            checks.append({'policy': policy, 'option': option, 'sigma': sigma,
                           'raw_attributes_ids_duration': 'PASS', 'route_oracle': 'PASS', 'published_metrics': 'PASS'})
        for option, sigma in cases:
            refs = [('M0', None)] + ([('R0', 1), ('R0', 2)] if option == 'M0' else [('R0', sigma)])
            for ref, ref_sigma in refs:
                a, b = frames[option, sigma], frames[ref, ref_sigma]
                for cohort, mask in masks.items():
                    value = pair(a[mask], b[mask])
                    mean_difference = metrics(a[mask])['mean_jct_hours'] - metrics(b[mask])['mean_jct_hours']
                    require(np.isclose(value['mean_finish_delta_hours'], mean_difference, atol=1e-9), 'paired mean/JCT identity')
                    reverse = pair(b[mask], a[mask])
                    require(np.isclose(value['mean_finish_delta_hours'], -reverse['mean_finish_delta_hours']) and
                            value['harmed_jobs'] == reverse['improved_jobs'], 'direct reverse identity')
                    pairs.append({'policy': policy, 'option': option, 'sigma': sigma, 'reference': ref,
                                  'reference_sigma': ref_sigma, 'cohort': cohort, **value})
                mask = masks['native_A100']
                invariant = {'policy': policy, 'option': option, 'sigma': sigma, 'reference': ref,
                             'reference_sigma': ref_sigma, 'n': int(mask.sum()),
                             'timing_equal': a[mask][['start', 'finish']].equals(b[mask][['start', 'finish']]),
                             'placement_equal': ledgers[option, sigma].equals(ledgers[ref, ref_sigma]),
                             'same_partition': option != 'M0' and ref == 'R0'}
                if invariant['same_partition']:
                    require(invariant['timing_equal'] and invariant['placement_equal'], 'native coupling')
                native.append(invariant)
    zip_source.close()
    for r in rows:
        for ref in ('M0', 'R0'):
            hit = [p for p in pairs if p['policy'] == r['policy'] and p['option'] == r['option'] and
                   p['sigma'] == r['sigma'] and p['cohort'] == r['cohort'] and p['reference'] == ref]
            # M0 has no same-sigma R0. Both reverse pairs remain explicitly available in paired.csv.
            selected = hit[0] if len(hit) == 1 else None
            for key in ('mean_finish_delta_hours', 'harmed_jobs', 'positive_finish_delay_job_hours'):
                r[f'vs_{ref}_{key}'] = selected[key] if selected else None
        n = next(p for p in pairs if p['policy'] == r['policy'] and p['option'] == r['option'] and
                 p['sigma'] == r['sigma'] and p['cohort'] == 'native_A100' and p['reference'] == 'M0')
        r['native_mean_wait_delta_vs_M0_hours'] = n['mean_wait_delta_hours']
        r['native_invariant_vs_R0'] = None if r['option'] == 'M0' else 'PASS'
    worst = discrete_worst(rows)
    args.out.mkdir(parents=True)
    for name, data in [('main_table', rows), ('paired', pairs), ('discrete_worst', worst), ('native_invariance', native)]:
        write_json(args.out / (name + '.json'), data)
        pd.DataFrame(data).to_csv(args.out / (name + '.csv'), index=False, na_rep='N/A')
    write_json(args.out / 'routing.json', routing)
    publish(args.out, rows, pairs, worst, routing)
    record(Path(__file__).resolve().relative_to(Path.cwd()))
    record(PROBLEM / 'tests/test_q3_v2_tradeoffs.py')
    report = {
        'kind': 'Q3-V2-R1 persisted-evidence postprocessing', 'new_scheduling_runs': 0,
        'candidate_B': 'IMPLEMENTATION_DEFERRED', 'horizon_seconds': H,
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'source_commit_scope': 'HEAD before publication commit; new generator/tests were uncommitted at execution',
        'baseline_tag_commit': subprocess.check_output(['git', 'rev-parse', '2026-mcm-b-baseline-v1^{commit}'], text=True).strip(),
        'command': ['python', *sys.argv], 'environment': {'python': sys.version, 'pandas': pd.__version__, 'numpy': np.__version__},
        'groups': {'A10': 111284, 'ALL': 224112, 'native_A100': 80877},
        'pair_definition': 'candidate minus named reference, aligned original ID; means over n, conditional means over harmed_jobs; null iff no harmed jobs',
        'quantiles': 'linear; full named cohort unless harmed_ prefix; each direction recomputed from timing',
        'checks': checks, 'paired_mean_and_reverse_identities': 'PASS',
        'native_timing_placement_vs_same_partition_R0': 'PASS',
        'physical_replay': 'NOT_RUN in R1; prior PASS in hashed V1/S2/V2 independent reports, not rerun scheduling',
        'prior_verifier_limit': 'V2 prior route check called production route_shape; R1 independently audits raw attributes, arithmetic eligibility, hash and shape IDs; no new physical replay claim',
        'historical_execution_count': 'not audited; new_scheduling_runs=0 refers only to R1',
        'sources': source,
        'delivery': {'status': 'LOCAL_ONLY', 'cross_machine': 'BLOCKED',
                     'archive': str(archive), **source[str(archive)],
                     'access': 'Authorized local filesystem read in this worktree; no remote/shared URI or transfer authorization established. Ask owner for an authorized copy; verify listed hash before extraction.',
                     'scope': 'Archive contains four R-shape timing/placement pairs only; M0 and R0 inputs are separately listed local sources.'},
        'result_sha256': {p.name: digest(p) for p in sorted(args.out.iterdir())},
    }
    write_json(args.out / 'manifest.json', report)
    print(json.dumps({'status': 'PASS', 'schedules_executed': 0, 'rows': len(rows), 'pairs': len(pairs), 'out': str(args.out)}))


if __name__ == '__main__':
    main()
