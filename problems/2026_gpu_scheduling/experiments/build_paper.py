#!/usr/bin/env python3
"""Build the integration draft, with recomputed Q1 and labeled archived Q2/Q3 figures."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROBLEM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROBLEM / 'src'))
from gpu_scheduling.q1 import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=PROBLEM / 'data/raw')
    parser.add_argument('--out', type=Path, required=True, help='New build directory')
    parser.add_argument('--compiler', help='Path/name of tectonic or pdflatex')
    args = parser.parse_args()
    compiler = shutil.which(args.compiler) if args.compiler else (shutil.which('tectonic') or shutil.which('pdflatex'))
    if not compiler:
        parser.error('BLOCKED: install tectonic or pdflatex, or provide --compiler PATH')
    if args.out.exists(): parser.error('Output exists; choose a new directory')
    out = args.out.resolve()
    nodes, jobs, stats = analyze(args.data, out / 'q1')
    subprocess.run([sys.executable, str(PROBLEM/'experiments/generate_figures.py'),
                    '--data', str(args.data.resolve()), '--results', str(out/'q1'),
                    '--out', str(out/'figures'), '--paper-reference'], check=True)
    import pandas as pd
    demand = pd.read_csv(out/'q1/immediate_start_demand.csv')
    pools = pd.read_csv(out/'q1/pool_summary.csv')
    aten = demand[(demand.gpu_model=='A10') & (demand.resource=='GPU')].iloc[0]
    ahundred = demand[(demand.gpu_model=='A100-SXM4-80GB') & (demand.resource=='GPU')].iloc[0]
    values = {
        'QOneAtenMean': f'{aten.immediate_start_mean:,.2f}',
        'QOneAtenCapacity': f'{aten.capacity:,.0f}',
        'QOneAtenExcess': f'{aten.immediate_start_mean-aten.capacity:,.2f}',
        'QOneAtenRho': f'{pools.loc[pools.gpu_model=="A10","rho_gpu"].iloc[0]:.3f}',
        'QOneAhundredPeak': f'{ahundred.immediate_start_peak:,.0f}',
        'QOneAtenCpu': f'{jobs.loc[jobs.gpu_model=="A10","cpu_request"].mean():.2f}',
    }
    (out/'q1_values.tex').write_text('% Generated from this build\'s raw CSV analysis.\n'+''.join(
        '\\newcommand{\\'+name+'}{'+value+'}\n' for name,value in values.items()))
    shutil.copyfile(PROBLEM/'paper/document_en.tex',out/'document_en.tex')
    for fig in (out/'figures').glob('*.pdf'): shutil.copyfile(fig,out/fig.name)
    version = subprocess.run([compiler,'--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]
    name = Path(compiler).name
    command = [compiler,'--keep-logs','--keep-intermediates','document_en.tex'] if 'tectonic' in name else [compiler,'-interaction=nonstopmode','-halt-on-error','document_en.tex']
    record = {'status':'NOT_RUN','compiler':version,'command':command,'data_sha256':stats['input_sha256'],
              'q1_values':values,'q2_q3_claims':'NOT_RUN; archived table figures only','files':{}}
    result = subprocess.run(command,cwd=out,capture_output=True,text=True)
    if result.returncode==0 and 'tectonic' not in name:
        result = subprocess.run(command,cwd=out,capture_output=True,text=True)
    (out/'compile.log').write_text(result.stdout+result.stderr)
    record['status'] = 'PASS' if result.returncode==0 else 'FAIL'
    record['page_limit'] = 'NOT_RUN'
    pdf=out/'document_en.pdf'
    if result.returncode==0 and shutil.which('pdfinfo'):
        info=subprocess.check_output(['pdfinfo',str(pdf)],text=True)
        (out/'pdfinfo.txt').write_text(info)
        record['pages']=int(re.search(r'Pages:\s+(\d+)',info).group(1))
        record['page_limit']='PASS' if record['pages']<=10 else 'FAIL'
    record['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    (out/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    if result.returncode: raise SystemExit('FAIL: LaTeX compile; see compile.log')
    print(f'PASS: compiled integration draft; page limit {record["page_limit"]}. Q2/Q3 claims remain NOT_RUN.')


if __name__=='__main__': main()
