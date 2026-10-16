"""Render Q1 prose values and tables from the audited outputs; no new formulas."""
from html import escape
from fractions import Fraction
import json
from pathlib import Path
import re
import pandas as pd

MODEL_NAMES = {'A100-SXM4-80GB': 'A100-80G', 'A800-SXM4-80GB': 'A800-80G',
               'GPU-series-1': 'GPU-s1', 'GPU-series-2': 'GPU-s2'}


def publication_values(results, jobs):
    stats = json.loads((results/'q1_results.json').read_text())
    pools = pd.read_csv(results/'pool_summary.csv')
    demand = pd.read_csv(results/'immediate_start_demand.csv')
    shapes = pd.read_csv(results/'resource_shape.csv')
    quantiles = pd.read_csv(results/'duration_quantiles.csv')
    concentration = pd.read_csv(results/'concentration.csv')
    configs = pd.read_csv(results/'node_configurations.csv')
    bounds = json.loads((results/'q1_capacity_bounds.json').read_text())
    aten = demand[(demand.gpu_model=='A10') & (demand.resource=='GPU')].iloc[0]
    ahundred = demand[(demand.gpu_model=='A100-SXM4-80GB') & (demand.resource=='GPU')].iloc[0]
    shape = shapes[(shapes.gpu_model=='GPU-series-1') & (shapes.gpus_per_node==8)].iloc[0]
    values = {}
    def put(name, number, decimals=0):
        values['QOne'+name] = f'{number:,.{decimals}f}'
    bound = bounds['pools']['A10']['lower_bound_hours']
    put('AtenWaitBound', float(Fraction(bound['numerator'], bound['denominator'])), 3)
    for name,key in [('Jobs','jobs'),('Nodes','nodes'),('Gpus','physical_gpus'),('Cpus','vcpus'),
                     ('Models','gpu_models'),('Horizon','horizon_seconds'),('WindowDifference','nominal_90day_difference_seconds'),
                     ('OriginJobs','t0_jobs'),('FractionalCpuJobs','fractional_cpu_jobs'),('ZeroCpuJobs','zero_cpu_jobs')]:
        put(name,stats[key])
    for name,key in [('MeanWorkers','mean_workers'),('MeanWorkerGpus','mean_gpu_per_worker')]: put(name,stats[key],3)
    for name,key in [('SingleWorkerPct','single_worker_jobs'),('OneGpuPct','one_gpu_per_worker_jobs')]: put(name,100*stats[key]/stats['jobs'],2)
    put('WorkMillion',stats['total_gpu_hours']/1e6,3)
    put('Gini',stats['gini_gpu_work'],4); put('DurationGini',stats['gini_duration'],4)
    put('MedianDuration',quantiles.loc[quantiles['quantile']==.5,'duration_seconds'].iloc[0])
    put('PninetyfiveDuration',quantiles.loc[quantiles['quantile']==.95,'duration_hours'].iloc[0],2)
    put('MaxDurationDays',stats['max_duration_seconds']/86400)
    put('HorizonHours',stats['horizon_hours'],3)
    put('PhasePeak',stats['peak_relative_hour']); put('PhaseTrough',stats['trough_relative_hour'])
    put('PhaseRatio',stats['phase_peak_trough_ratio'],2)
    for fraction,name in [(.001,'PointOne'),(.01,'One'),(.05,'Five')]:
        row=concentration[(concentration.gpu_model=='ALL') & (concentration.nominal_top_fraction==fraction)].iloc[0]
        put('Top'+name+'Count',row.jobs_selected);put('Top'+name+'Share',100*row.work_share,2)
    for name,number,decimals in [('AtenMean',aten.immediate_start_mean,2),('AtenCapacity',aten.capacity,0),
        ('AtenExcess',aten.immediate_start_mean-aten.capacity,2),('AtenPeak',aten.immediate_start_peak,0),
        ('AtenMeanPct',aten.immediate_start_mean_ratio*100,2),('AtenRho',pools.loc[pools.gpu_model=='A10','rho_gpu'].iloc[0],3),
        ('AhundredPeak',ahundred.immediate_start_peak,0),('AtenCpu',jobs.loc[jobs.gpu_model=='A10','cpu_request'].mean(),2),
        ('RatioThreshold',shape.node_cpu_per_gpu,0),('HighRatioJobs',shape.jobs_above_ratio,0),
        ('HighRatioPct',shape.fraction_jobs_above_ratio*100,2),('HighRatioWorkPct',shape.work_share_above_ratio*100,2)]: put(name,number,decimals)
    for gpu,cpu,name in [(1,128,'OneSmallNodes'),(1,192,'OneNodes'),(4,192,'FourNodes'),(8,192,'EightNodes')]:
        rows=configs[(configs.gpu_model=='GPU-series-1') & (configs.gpu_capacity_num==gpu) & (configs.cpu_num==cpu)]
        put(name,rows.nodes.sum())
    return values,pools


def substitute_html(template, values):
    def replace(match):
        key=match.group(1)
        if key not in values: raise ValueError(f'Unknown Q1 HTML value: {key}')
        return escape(str(values[key]))
    return re.sub(r'@@(QOne[A-Za-z]+)@@',replace,template)


def write_publication(results, jobs, paper, out):
    values,pools=publication_values(results,jobs)
    (out/'q1_values.json').write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'q1_values.tex').write_text('% Generated from audited Q1 outputs.\n'+''.join(
        '\\newcommand{\\'+name+'}{'+value+'}\n' for name,value in values.items()),encoding='utf-8')
    tex_rows=[]; html_rows=[]
    for row in pools.itertuples():
        fields=[MODEL_NAMES.get(row.gpu_model,row.gpu_model),f'{row.physical_gpus:,}',f'{row.jobs:,}',
                f'{row.gpu_hours/1e6:.3f}',f'{row.rho_gpu:.3f}',f'{row.rho_cpu:.3f}']
        tex_rows.append(' & '.join(fields)+r' \\')
        html_rows.append('<tr>'+''.join('<td>'+escape(x)+'</td>' for x in fields)+'</tr>')
    table = r"\begin{tabular}{lrrrrr}\toprule" + "\n" + r"Model & GPUs & Jobs & Work & $\rho^{\mathrm{GPU}}$ & $\rho^{\mathrm{CPU}}$ \\" + "\n" + r"\midrule" + "\n" + "\n".join(tex_rows) + "\n" + r"\bottomrule\end{tabular}" + "\n"
    (out/'q1_table.tex').write_text(table,encoding='utf-8')
    html=substitute_html((paper/'q1_zh.html').read_text(encoding='utf-8'),values)
    if html.count('@@POOL_ROWS@@')!=1: raise ValueError('Missing/duplicate HTML table marker')
    html=html.replace('@@POOL_ROWS@@','\n'.join(html_rows))
    if '@@' in html: raise ValueError('Unresolved HTML value')
    (out/'q1_zh.html').write_text(html,encoding='utf-8')
    # Catch unresolved source macros before invoking the typesetter.
    for name in ['q1_section.tex','q1_summary.tex']:
        text=(paper/name).read_text(encoding='utf-8')
        unknown=set(re.findall(r'\\(QOne[A-Za-z]+)',text))-set(values)
        if unknown: raise ValueError(f'Unknown Q1 TeX values in {name}: {sorted(unknown)}')
    return values
