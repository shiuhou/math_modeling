"""Read-only evidence inventory and publication tables; never runs a scheduler.
Run from repository root: .venv/bin/python results/20261018-b-q2-v2-r1-01/build_revision.py
"""
from pathlib import Path
import hashlib, json, subprocess, time, resource, shutil
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
OLD = ROOT / 'results/20261017-b-q2-v2-01'
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()
def dump(name, obj):
    (OUT/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
def canonical(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
start=time.perf_counter()
old_hashes={str(p.relative_to(ROOT)):sha(p) for p in OLD.rglob('*') if p.is_file()}
x=json.loads((OLD/'comparison.json').read_text())
index={}; tables=[]; cmds=[]
(OUT/'summaries').mkdir(exist_ok=True)
for label, source in x['source'].items():
    name='q2-v2-'+label.lower()
    bp=OLD/'benchmarks'/f'{name}.json'
    b=json.loads(bp.read_text()); r=b['records'][0]
    child=ROOT/source['child_output']; sp=child/'summary.json'
    entry={'benchmark':{'path':str(bp.relative_to(ROOT)), 'sha256':sha(bp),'availability':'REPOSITORY_AVAILABLE'},
           'config_sha256':canonical(b['configuration']), 'config_hash_serialization':'UTF-8 JSON sort_keys=True separators comma/colon',
           'job_id_sha256':source['job_id_sha256'], 'id_serialization':'sorted decimal IDs joined by LF, NO trailing LF',
           'artifacts':[], 'separate_persisted_replay':{'availability':'MISSING','status':'NOT_AVAILABLE'},
           'same_timestamp_unique_repeated':'NOT_AVAILABLE'}
    if sp.exists():
        assert sha(sp)==r['child_summary_sha256'], label
        s=json.loads(sp.read_text())
        assert s['results'][0]['metrics']==r['metrics']
        assert s['results'][0]['schedule_sha256']==r['schedule_sha256']
        dest=OUT/'summaries'/f'{name}.json'; shutil.copyfile(sp,dest)
        entry.update(run_commit=s['code_commit'],run_dirty=s['code_dirty'],source_sha256=s['source_sha256'],data_sha256=s['data_sha256'],
            summary={'path':str(dest.relative_to(ROOT)),'sha256':sha(dest),'availability':'REPOSITORY_AVAILABLE'},
            historical_validation={'status':s['results'][0]['validation'],'scope':'in-process independent capacity and reservation replay, not a separate persisted replay'})
        for file, expected in s['outputs'].items():
            p=child/file
            actual=sha(p) if p.exists() else None
            if actual is not None: assert actual==expected,(label,file)
            entry['artifacts'].append({'path':str(p.relative_to(ROOT)),'expected_sha256':expected,'actual_sha256':actual,
                'availability':'LOCAL_ONLY' if p.exists() else 'MISSING', 'hash_match':actual==expected})
        for file,h in s['data_sha256'].items(): assert sha(ROOT/'problems/2026_gpu_scheduling/data/raw'/file)==h
        # Source hash match is stronger than the old stale self-referential commit field.
        entry['current_source_matches_run']={p:sha(ROOT/p)==h for p,h in s['source_sha256'].items()}
        assert all(entry['current_source_matches_run'].values())
    else: entry['summary']={'path':str(sp.relative_to(ROOT)),'availability':'MISSING'}
    cfg=b['configuration']
    command=f".venv/bin/python problems/2026_gpu_scheduling/experiments/run_m2b_benchmark.py --jobs {r['jobs']} --theta-seconds 604800 --short-theta-seconds 604800 --reservation-k {cfg['reservation_k']} --event-mode {cfg['event_mode']} --policies {r['policy']} --timeout-seconds 900 --max-rss-kib 4194304 --out outputs/{name}"
    entry['reconstructed_original_command']=command
    entry['command_note']='Reconstructed from saved config; not executed in R1. Existing output path refuses overwrite.'
    cmds.append(command); index[label]=entry
for size, group in x['results_by_job_count'].items():
    tables += [f'## A10 {size} jobs', '', 'Waiting/JCT in hours; elapsed costs in seconds; RSS in MiB.','',
        '|Config|Mean|P99|Max|JCT|90d complete|Child wall|Scheduler incl. capacity|Reservation validator|I/O+hash|RSS|Promises|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for label,p in group['policies'].items():
        r=json.loads((OLD/'benchmarks'/('q2-v2-'+label.lower()+'.json')).read_text())['records'][0]
        assert p['metrics']==r['metrics']
        m=p['metrics']; values=[m[k] for k in ['mean_wait_hours','p99_wait_hours','max_wait_hours','mean_jct_hours']]
        tables.append('|'+label+'|'+ '|'.join(f'{v:.6f}' for v in values)+f"|{m['completed_at_horizon']}|{r['child_wall_seconds']:.3f}|{r['scheduler_seconds']:.3f}|{r['validation_seconds']:.3f}|{r['io_seconds']:.3f}|{r['peak_rss_kib_process']/1024:.3f}|{r['reservations']}|")
    tables += ['', '|Config/group|n|Mean h|P99 h|Max h|','|---|---:|---:|---:|---:|']
    for label,p in group['policies'].items():
        for g,v in p['groups'].items(): tables.append(f"|{label}/{g}|{v['n']}|{v['mean_wait_hours']:.6f}|{v['p99_wait_hours']:.6f}|{v['max_wait_hours']:.6f}|")
    tables += ['']
tables += ['## Preserved ID-paired comparisons (candidate minus base)', '', '|Pair|Improved|Harmed|Positive added job-seconds|Max added h|Mean delta h|','|---|---:|---:|---:|---:|---:|']
for k,v in x['pairs'].items(): tables.append(f"|{k}|{v['improved_jobs']}|{v['worsened_jobs']}|{v['positive_added_wait_job_seconds']}|{v['max_added_wait_hours']:.6f}|{v['mean_delta_hours']:.6f}|")
(OUT/'tables.md').write_text('\n'.join(tables)+'\n')
dump('evidence_index.json',index)
dump('exact_comparison.json',{'results_by_job_count':x['results_by_job_count'],'pairs':x['pairs']})
(OUT/'commands.sh').write_text('# Evidence only: historical commands below are NOT executed by R1.\n'+ '\n'.join('# '+c for c in cmds)+'\n# R1 read-only generation:\n.venv/bin/python results/20261018-b-q2-v2-r1-01/build_revision.py\n')
f=x['results_by_job_count']['111284']['policies']; hol=f['full-H1']['metrics']; head=f['full-C1']['metrics']
ratios={}
for prefix in ['65k','full']:
 for a,b in [('A1','A2'),('A3','A4')]:
    recs=[json.loads((OLD/'benchmarks'/f'q2-v2-{prefix}-{k.lower()}.json').read_text())['records'][0] for k in (a,b)]
    ratios[f'{prefix}-{b}/{a}']=recs[1]['scheduler_seconds']/recs[0]['scheduler_seconds']
dump('cost_ratios.json',{'scheduler_elapsed_ratios_same_event_mode':ratios,'cpu_time':'NOT_AVAILABLE'})
en=f"""Across the two tested A10 sizes, K=200/2000, and the two tested event modes, ordinary SPT-HOL has the lowest job-count mean waiting. It has no aging: theta=604800 s supplies shared timer opportunities and is not a HOL priority parameter. These results do not establish superiority over all K values or unbounded FILL. Increasing K did not improve FILL's mean, although some full-trace tail statistics improved. Same-mode scheduler elapsed-time ratios (K2000/K200) are {json.dumps(ratios,sort_keys=True)}; process CPU time was not recorded.\n\nOn full A10, HEAD-TIME versus ordinary HOL changes mean waiting from {hol['mean_wait_hours']:.6f} to {head['mean_wait_hours']:.6f} h, P99 from {hol['p99_wait_hours']:.6f} to {head['p99_wait_hours']:.6f} h, and maximum from {hol['max_wait_hours']:.6f} to {head['max_wait_hours']:.6f} h. This is a trade-off, not uniform tail improvement or Pareto dominance. Successful promise tests and in-process replay support the tested safety contract, not general starvation freedom, bounded waiting, or performance guarantees. Retain ordinary HOL as the primary mean-waiting method, the K/timer matrix as bounded robustness evidence, and HEAD-TIME as an experimental option with negative cost evidence. Group and paired tables retain harms. The lower-bound decomposition is accounting, not a causal attribution or an exactly removable OPT gap.\n"""
zh=f"""在兩個已測 A10 規模、K=200／2000 與兩種事件模式中，普通 SPT-HOL 的作業計數平均等待最低。普通 HOL 沒有 aging；theta=604800 秒只提供共享 timer 派工機會，不是 HOL 優先權參數。結果不外推至所有 K 或無上限 FILL。提高 K 未改善 FILL 平均等待，但完整 A10 部分尾部指標改善。同事件模式下 K2000/K200 的 scheduler 經過時間比為 {json.dumps(ratios,sort_keys=True)}；未記錄 process CPU time。\n\n完整 A10 中，HEAD-TIME 相對普通 HOL 的 Mean 由 {hol['mean_wait_hours']:.6f} 增至 {head['mean_wait_hours']:.6f} 小時，P99 由 {hol['p99_wait_hours']:.6f} 降至 {head['p99_wait_hours']:.6f} 小時，Max 由 {hol['max_wait_hours']:.6f} 增至 {head['max_wait_hours']:.6f} 小時。這是取捨，不是尾部全面改善或 Pareto 支配。已通過的 promise 測試與程序內獨立回放只支持所測安全契約，不保證一般無飢餓、等待上界或性能。普通 HOL 維持平均等待主方案；K/timer 矩陣作有界穩健性證據；HEAD-TIME 保留為實驗選項及成本負面結果。分組和配對表保留受損作業；下界分解是記帳，不是因果份額或可全部消除的 OPT gap。\n"""
(OUT/'results_en.md').write_text(en); (OUT/'results_zh.md').write_text(zh)
assert old_hashes=={str(p.relative_to(ROOT)):sha(p) for p in OLD.rglob('*') if p.is_file()}
dump('manifest.json',{'revision':'Q2-V2-R1','base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'original_files_sha256':old_hashes,'original_files_unchanged':'PASS','numeric_copy_regression':'PASS',
 'scheduler_runs':0,'availability':'14 run artifacts LOCAL_ONLY; compact summaries/index REPOSITORY_AVAILABLE; separate persisted replay reports MISSING',
 'validation_scope':'hash/index/summary consistency only; no new capacity or reservation replay',
 'analysis_seconds':time.perf_counter()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
 'generator_sha256':sha(Path(__file__)), 'files_sha256':{str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}})
print('PASS: 14 source summaries, artifact hashes, exact numeric copy; old results unchanged')
