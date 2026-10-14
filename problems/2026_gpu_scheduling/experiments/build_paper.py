#!/usr/bin/env python3
"""Recompute Q1, render both languages and figures, and compile Q1 or the full draft."""
import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from zipfile import ZipFile, ZIP_DEFLATED

PROBLEM = Path(__file__).resolve().parents[1]
REPO = PROBLEM.parents[1]
sys.path.insert(0,str(PROBLEM/'src'))
import numpy as np
import pandas as pd
import matplotlib
from gpu_scheduling.q1 import analyze
from gpu_scheduling.q1_publication import write_publication


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def source_files():
    modules=['__init__.py','data.py','q1.py','q1_publication.py']
    scripts=['build_paper.py','generate_figures.py','eda_analysis.py','eda_deep.py','verify_q1.py']
    papers=['preamble.tex','document_en.tex','q1_section.tex','q1_summary.tex','q1_zh.html']
    return ([PROBLEM/'src/gpu_scheduling'/n for n in modules]+
            [PROBLEM/'experiments'/n for n in scripts]+[PROBLEM/'paper'/n for n in papers]+
            [PROBLEM/'requirements.txt',PROBLEM/'tests/test_q1.py'])


def version_record():
    def git(*args):
        result=subprocess.run(['git',*args],cwd=REPO,capture_output=True,text=True)
        return result.stdout.strip() if result.returncode==0 else None
    own_repo=git('rev-parse','--show-toplevel') == str(REPO)
    commit=git('rev-parse','HEAD') if own_repo else None
    status=git('status','--porcelain') if own_repo else None
    return {'commit':commit,'dirty':bool(status) if status is not None else None,
            'sha256':{str(p.relative_to(REPO)):sha(p) for p in source_files()},
            'snapshot':'source/ (all participating Q1 sources, including dirty changes)'}


def supplementary_html(out):
    figures=[('supplement_model_distributions','S1. 分型號 Lorenz 曲線與嚴格 Duration CCDF；含所有六型號。'),
             ('supplement_supply_shares','S2. 容量、提交作業與完整生命週期 GPU 工作量的份額；不是利用率。'),
             ('supplement_daily_arrivals_work','S3. 每日提交量與完整生命週期工作量；另顯示排除時間零批次的曲線。最後一天不足 24 小時，這裡呈現總量，不是校正後速率。'),
             ('supplement_relative_phase','S4. 排除時間零提交、按實際 exposure 校正的相對 24 小時相位；沒有現實時區含義。'),
             ('supplement_resource_shape','S5. GPU-series-1 作業超過各節點 CPU/GPU 配比的比例。門檻彼此重疊，不可相加為互斥類別；不代表實際擱淺量。')]
    pieces=['<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>Q1 補充圖表</title>',
            '<style>body{max-width:1100px;margin:32px auto;padding:0 20px;font:17px/1.65 system-ui,sans-serif;color:#203040}img{max-width:100%}table{border-collapse:collapse;font-size:15px}td,th{border:1px solid #ccd5dc;padding:6px}section{overflow:auto}figure{margin:30px 0}</style>',
            '<h1>Q1 補充圖表與核算明細</h1><p><a href="q1_zh.html">中文對照</a> · <a href="q1_en.pdf">英文正文</a>。補充資料不計入兩頁 Q1 預覽；不證明 Q2/Q3 性能。</p>']
    for name,caption in figures:
        pieces.append(f'<figure><img src="figures/{name}.png" alt="{escape(caption)}"><figcaption>{escape(caption)} <a href="figures/{name}.pdf">向量 PDF</a></figcaption></figure>')
    for name in ['node_configurations.csv','resource_shape.csv','pool_summary.csv','immediate_start_demand.csv','concentration.csv','duration_quantiles.csv']:
        frame=pd.read_csv(out/'q1'/name)
        pieces.append(f'<section><h2>{name}</h2><a href="q1/{name}">原始精度 CSV</a>'+frame.to_html(index=False,float_format=lambda x:f'{x:.6g}')+'</section>')
    pieces.append('<h2>完整核算檔案</h2><ul>'+''.join(f'<li><a href="q1/{p.name}">{p.name}</a></li>' for p in sorted((out/'q1').iterdir()))+'</ul></html>')
    (out/'supplementary.html').write_text('\n'.join(pieces),encoding='utf-8')


def compile_tex(compiler,source,out):
    tectonic='tectonic' in Path(compiler).name.lower()
    options=['--keep-logs','--keep-intermediates'] if tectonic else ['-interaction=nonstopmode','-halt-on-error']
    command=[compiler,*options,source+'.tex'];logs=[];returncode=0
    for _ in range(1 if tectonic else 2):
        result=subprocess.run(command,cwd=out,capture_output=True,text=True)
        logs.append(result.stdout+result.stderr);returncode=result.returncode
        if returncode:break
    (out/(source+'_compile.log')).write_text('\n'.join(logs),encoding='utf-8')
    item={'status':'PASS' if returncode==0 else 'FAIL','command':[Path(compiler).name,*options,source+'.tex'],'pages':None,'page_limit':'NOT_RUN'}
    if returncode==0 and shutil.which('pdfinfo'):
        info=subprocess.check_output(['pdfinfo',str(out/(source+'.pdf'))],text=True)
        (out/(source+'_pdfinfo.txt')).write_text(info)
        item['pages']=int(re.search(r'Pages:\s+(\d+)',info).group(1))
        limit=2 if source=='q1_en' else 10
        item['page_limit']='PASS' if item['pages']<=limit else 'FAIL'
    return item


def delivery_readme(out,record):
    commit=record['code']['commit'] or 'see source_version.json'
    (out/'DELIVERY.txt').write_text(f'''Q1 research delivery / 第一問交付

Read q1_en.pdf (English), q1_zh.html (Traditional Chinese), supplementary.html.
Open HTML from this directory; keep figures/ and q1/ alongside it. No network is needed to read them.
Source base commit: {commit}; exact participating bytes are recorded in build.json and included under source/.
A dirty build is reproducible from the included source snapshot; the commit alone is not its exact source.

Reproduce from a clone (no ChatGPT attachments needed):
  git clone -b feat/b-q1 https://github.com/shiuhou/math_modeling.git
  cd math_modeling
  python3 -m venv .venv
  .venv/bin/python -m pip install -r problems/2026_gpu_scheduling/requirements.txt
  .venv/bin/python problems/2026_gpu_scheduling/experiments/build_paper.py --scope q1 --out outputs/q1-new --bundle

Use Python 3.11+ and install tectonic (tested 0.17.0) or pdflatex separately.
Pass --compiler PATH if it is not on PATH; first TeX use may download packages.
Windows: replace .venv/bin/python with .venv\\Scripts\\python.exe.
Outputs must be new directories. No scheduling experiment is run by this command.

To reproduce EXACT included source bytes without Git: install requirements from source/,
then run source/problems/2026_gpu_scheduling/experiments/build_paper.py --scope q1
--data /path/to/clone/problems/2026_gpu_scheduling/data/raw --out /path/to/new-build.
The two raw CSVs are already tracked in the repository; they are not duplicated in this ZIP.
Input SHA-256: {json.dumps(record['data_sha256'],ensure_ascii=False)}

Evidence: build.json, q1_figure.json (in figures/), numeric q1/*.csv and q1/q1_results.json.
Compiler success does not prove final paper readiness. Q2/Q3 claims are NOT_RUN.
Historical raw-job byte identity, public redistribution scope, team names and human approval remain unconfirmed.
Codex assisted with integration, calculations, bilingual prose, plots and typesetting.
''',encoding='utf-8')


def bundle_delivery(out):
    target=out/'Q1_delivery.zip'
    # Avoid duplicate staged figures and TeX scratch files; retain all numeric/source evidence.
    roots=['q1_en.pdf','q1_zh.html','supplementary.html','DELIVERY.txt','build.json','q1_values.json',
           'q1_values.tex','q1_table.tex','q1_en_compile.log','source_version.json']
    files=[out/n for n in roots if (out/n).is_file()]
    for folder in ['q1','figures','source']:
        files.extend(p for p in (out/folder).rglob('*') if p.is_file()
                     and not (folder=='figures' and (p.name.startswith(('fig2_', 'fig3_')) or p.name=='paper_reference_figures.json')))
    with ZipFile(target,'w',ZIP_DEFLATED) as archive:
        for path in sorted(files):archive.write(path,str(path.relative_to(out)))
    if target.stat().st_size>=50_000_000:raise ValueError('Delivery ZIP exceeds 50 MB')
    write_json(out/'bundle.json',{'file':target.name,'bytes':target.stat().st_size,'sha256':sha(target),'raw_data_included':False})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=PROBLEM/'data/raw')
    parser.add_argument('--out',type=Path,required=True,help='New build directory')
    parser.add_argument('--compiler',help='Path/name of tectonic or pdflatex')
    parser.add_argument('--scope',choices=['q1','full'],default='full')
    parser.add_argument('--bundle',action='store_true',help='Package Q1 deliverables and reproducible source, excluding raw data')
    args=parser.parse_args()
    compiler=shutil.which(args.compiler) if args.compiler else (shutil.which('tectonic') or shutil.which('pdflatex'))
    if not compiler:parser.error('BLOCKED: install tectonic or pdflatex, or provide --compiler PATH')
    if args.out.exists():parser.error('Output exists; choose a new directory')
    start=time.perf_counter();out=args.out.resolve();out.mkdir(parents=True)
    record={'status':'NOT_RUN','scope':args.scope,'created_at_utc':datetime.now(timezone.utc).isoformat(),
            'code':version_record(),'command':['python','problems/2026_gpu_scheduling/experiments/build_paper.py',*sys.argv[1:]],
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'platform':platform.platform()},
            'q2_q3_claims':'NOT_RUN; optional full build only renders archived claims',
            'validation':{'q1_computation':'NOT_RUN','q1_compile':'NOT_RUN','full_compile':'NOT_RUN','visual_review':'NOT_RUN','bilingual_human_review':'NOT_RUN'},
            'open_items':['Historical input job byte identity','Data redistribution scope','Team names and final AI disclosure','Human review'],
            'submission_ready':False,'files':{}}
    for path in source_files():
        dest=out/'source'/path.relative_to(REPO);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
    write_json(out/'source_version.json',record['code'])
    try:
        nodes,jobs,stats=analyze(args.data,out/'q1')
        record['data_sha256']=stats['input_sha256'];record['validation']['q1_computation']='PASS'
        command=[sys.executable,str(PROBLEM/'experiments/generate_figures.py'),'--data',str(args.data.resolve()),
                 '--results',str(out/'q1'),'--out',str(out/'figures'),'--figures','all']
        if args.scope=='full':command.append('--paper-reference')
        subprocess.run(command,check=True)
        record['q1_values']=write_publication(out/'q1',jobs,PROBLEM/'paper',out)
        for name in ['preamble.tex','q1_section.tex','q1_summary.tex']:
            shutil.copyfile(PROBLEM/'paper'/name,out/name)
        for fig in (out/'figures').glob('*.pdf'):shutil.copyfile(fig,out/fig.name)
        (out/'q1_en.tex').write_text(r'''\input{preamble.tex}
\setlength{\headheight}{14pt}
\fancyhead[L]{\fontsize{11.1}{13.3}\selectfont\color{graytext}2026 MCM Problem B}
\fancyhead[R]{\fontsize{11.1}{13.3}\selectfont\color{graytext}Question 1}
\fancyfoot[C]{\fontsize{11.1}{13.3}\selectfont\thepage}
\begin{document}
\input{q1_section.tex}
\end{document}
''',encoding='utf-8')
        record['compiler']=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0]
        record['q1_build']=compile_tex(compiler,'q1_en',out)
        record['validation']['q1_compile']=record['q1_build']['status']
        if record['q1_build']['status']=='FAIL':raise RuntimeError('LaTeX failed: inspect q1_en_compile.log')
        supplementary_html(out)
        if args.scope=='full':
            shutil.copyfile(PROBLEM/'paper/document_en.tex',out/'document_en.tex')
            record['full_build']=compile_tex(compiler,'document_en',out)
            record['validation']['full_compile']=record['full_build']['status']
            if record['full_build']['status']=='FAIL':raise RuntimeError('LaTeX failed: inspect document_en_compile.log')
            record['full_format_limitations']='Q2/Q3 archived wide tables and headers remain outside Q1 typography acceptance'
        record['status']='FAIL' if any(record[key]['page_limit']=='FAIL' for key in ['q1_build','full_build'] if key in record) else 'PASS'
        delivery_readme(out,record)
    except Exception as exc:
        record['status']='FAIL';record['error']=str(exc);raise
    finally:
        record['duration_seconds']=time.perf_counter()-start
        record['files']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='build.json'}
        write_json(out/'build.json',record)
    if record['status']!='PASS':raise SystemExit('FAIL: page limit exceeded; inspect build.json and PDFs')
    if args.bundle:bundle_delivery(out)
    print(f'PASS: {args.scope} build; Q1 {record["q1_build"]["pages"]} pages. Visual/human review recorded separately.')


if __name__=='__main__':main()
