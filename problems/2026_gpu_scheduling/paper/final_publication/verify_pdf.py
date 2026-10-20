#!/usr/bin/env python3
"""Extract the actual PDF cells and compare to formal evidence, including typography."""
import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
import fitz

ROOT=Path(__file__).resolve().parents[4]
def norm(s):
    return unicodedata.normalize('NFKC',s).replace('−','-').replace('ﬁ','fi').replace('ﬂ','fl')
def numbers(s):
    return re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?',norm(s))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pdf',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    doc=fitz.open(a.pdf);pages=[norm(pg.get_text()) for pg in doc];blocks=[(i+1,norm(b[4])) for i,pg in enumerate(doc) for b in pg.get_text('blocks')]
    text='\n'.join(pages);flat=re.sub(r'\s+',' ',text).replace('- filtered','-filtered')
    r2=json.loads((ROOT/'results/20261019-paper-content-r2/r2_metrics.json').read_text())
    runtime={x['case']:x for x in json.loads((ROOT/'results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json').read_text())['cases']}
    paired={x['case']:x for x in json.loads((ROOT/'results/20261020-final-publication/saved_timing_checks.json').read_text())['records']}
    generated=json.loads(Path(__file__).with_name('generated').joinpath('numerical_source_map.json').read_text())
    checks=[]
    def record(item,actual,expected,source,page=None):
        ok=actual==expected
        checks.append({'item':item,'status':'PASS' if ok else 'FAIL','pdf_actual':actual,'expected':expected,'source':source,'page':page})
        return ok
    # Numeric table blocks are selected by their first row, never by a caption keyword alone.
    t5=[(page,b) for page,b in blocks if re.match(r'No substitution\s+—',b)]
    assert len(t5)==2,'Table 5 extraction ambiguous: manual cell review required'
    parsed={}
    for part,(page,block) in zip(['performance','harm'],t5):
        rows=re.findall(r'(No substitution|Hash-10%|Shape-filtered)\s+(.*?)(?=No substitution|Hash-10%|Shape-filtered|\Z)',block,re.S)
        assert len(rows)==5
        for (label,body),case in zip(rows,['C0','C1','C2','C3','C4']):
            nums=numbers(body);expected_sigma=None if case=='C0' else runtime[case]['config']['sigma']
            if case=='C0':record(f'{part}.{case}.sigma','—' if body.lstrip().startswith('—') else body[:5],'—','No substitution has no foreign partition',page)
            else:record(f'{part}.{case}.sigma',int(nums.pop(0)),expected_sigma,f'{case}.config.sigma',page)
            record(f'{part}.{case}.label',label,generated['records'][int(case[1])]['display'],f'{case} routing mapping',page)
            if part=='performance':
                paths=[('a10_wait','original_A10','mean_wait_hours'),('a10_jct','original_A10','mean_jct_hours'),('all_jct','ALL','mean_jct_hours'),('done','ALL','completed_at_horizon')]
                assert len(nums)==4
                for actual,(field,cohort,key) in zip(nums,paths):
                    v=runtime[case]['metrics']['cohorts'][cohort][key];expected=f'{v:,}' if field=='done' else f'{v:.3f}'
                    record(f'Table5.{case}.{field}',actual,expected,f'v2_runtime_equivalence.json case={case}.metrics.cohorts.{cohort}.{key}',page)
                parsed[case]={'done':int(nums[-1].replace(',',''))}
            else:
                assert len(nums)==2
                for actual,key in zip(nums,['native_a100_wait_increase_count','a10_later_finish_count']):record(f'Table5.{case}.{key}',actual,f'{paired[case][key]:,}',f'saved_timing_checks.json case={case}.{key}; historical pair and C0 timing comparisons',page)
    t2=next((page,b) for page,b in blocks if re.match(r'A10\s+111,284',b))
    labels=[('A10','A10'),('A100','A100-SXM4-80GB'),('GS1','GPU-series-1'),('GS2','GPU-series-2'),('H800','H800'),('A800','A800-SXM4-80GB')]
    rows=re.findall(r'(A10|A100|GS1|GS2|H800|A800)\s+(.*?)(?=\bA10\b|\bA100\b|\bGS1\b|\bGS2\b|\bH800\b|\bA800\b|\Z)',t2[1],re.S)
    assert len(rows)==6
    total=0
    for (label,body),(expected_label,key) in zip(rows,labels):
        v=r2['q2_c0_six_pool'][key];values=numbers(body)
        expected=[f"{v['jobs']:,}",f"{v['gpus']:,}"]+[f'{v[k]:.3f}' for k in ['mean_wait_h','median_wait_h','p99_wait_h']]+[f'{100*v[k]:.3f}' for k in ['gpu_alloc','cpu_alloc']]+[f"{v['done90']:,}"]
        record('Table2.'+key,values,expected,f'r2_metrics.q2_c0_six_pool.{key}; formal C0',t2[0]);total+=int(values[-1].replace(',',''))
    record('Table2.sum_equals_Table5.C0',total,parsed['C0']['done'],'sum actual PDF six pools vs actual PDF C0',t2[0])
    t3=next((page,b) for page,b in blocks if b.startswith('FCFS\n'))
    for policy,key in [('FCFS','FCFS_B1'),('SPT-HOL','SPT-HOL_C0'),('SPT-FILL','SPT-FILL_full-A1')]:
        b=re.search(re.escape(policy)+r'\s+(.*?)(?=\bSPT-HOL\b|\bSPT-FILL\b|\Z)',t3[1],re.S).group(1)
        expected=[f"{r2['q2_a10_three_policy'][key][k]:.3f}" for k in ['mean_wait_h','p99_wait_h','max_wait_h','gpu_work_weighted_mean_wait_h']]
        record('Table3.'+policy,numbers(b),expected,'r2_metrics.q2_a10_three_policy.'+key,t3[0])
    strata=[]
    for key,pattern in [('W=1',r'^W\s*=\s*1\n'),('W=2-8',r'^W\s*=\s*2–8\n'),('W>=9',r'^W\s*≥\s*9\n')]:
        page,b=next((pg,b) for pg,b in blocks if re.match(pattern,b));v=r2['q2_worker_strata'][key]
        values=numbers(re.sub(pattern,'',b));expected=[f"{v['jobs']:,}"]+[f'{v[k]:.3f}' for k in ['hol_mean_wait_h','fill_mean_wait_h','hol_p99_wait_h','fill_p99_wait_h']]+[f"{v['paired_diff_h']:+.3f}"]+[f'{v[k]:,}' for k in ['improved_hol','worsened_hol','unchanged']]
        record('Table4.'+key,values,expected,'r2_metrics.q2_worker_strata.'+key+'; full-H1/full-A1',page)
        strata.append([float(x.replace(',','')) for x in values])
    N=sum(x[0] for x in strata);counts=[int(sum(x[i] for x in strata)) for i in [6,7,8]]
    record('Table4.paired_counts',counts,[55266,50575,5443],'sum extracted Table4 counts')
    record('Table4.population',int(N),111284,'complete original A10')
    record('Table4.count_partition',sum(counts),int(N),'actual PDF stratum outcomes partition population')
    for col,pol in [(1,'SPT-HOL_C0'),(2,'SPT-FILL_full-A1')]:
        displayed=sum(x[0]*x[col] for x in strata)/N;exact=r2['q2_a10_three_policy'][pol]['mean_wait_h']
        # Each printed mean is rounded to 0.001 h, so its weighted mean has the same bound.
        checks.append({'item':'Table4.weighted_mean.'+pol,'pdf_actual':displayed,'expected_exact':exact,'display_rounding_bound':0.0005,'status':'PASS' if abs(displayed-exact)<=0.0005 else 'FAIL','source':'PDF stratum counts and means; exact formal total'})
    for cohort in ['all','A10']:
        v=r2['q1_type_stats'][cohort]
        for k in ['duration_le_1h','duration_gt_24h']:
            for field in ['fraction','gpu_work_fraction']:
                val=f'{100*v[k][field]:.3f}%';record(f'Table1.{cohort}.{k}.{field}',val if val in pages[0] else None,val,'r2_metrics.q1_type_stats; formal raw CSV',1)
    allocation=text[text.index('The A100 allocation uses'):text.index('The aggregate capacity conversion')]
    own=allocation.split('The full-pool contributions')[0];contrib=allocation.split('The full-pool contributions')[1].split('and each')[0];totals=allocation.split('giving ')[1].split('Thus')[0]
    expected_own=[];expected_contrib=[];expected_totals=[]
    for case in ['C1','C2','C3','C4']:
        v=paired[case]['allocation']
        expected_own.extend(f"{v[k]['own_rate']:.6f}" for k in ['A100-SXM4-80GB','A100-foreign'])
        expected_contrib.extend(f"{v[k]['full_pool_contribution']:.6f}" for k in ['A100-SXM4-80GB','A100-foreign'])
        expected_totals.append(f"{v['full_pool_rate']:.6f}")
        from_seconds=sum(v[k]['window_gpu_seconds'] for k in ['A100-SXM4-80GB','A100-foreign'])/(3456*7776000)
        weighted=(2976*v['A100-SXM4-80GB']['own_rate']+480*v['A100-foreign']['own_rate'])/3456
        checks.append({'item':'allocation.identity.'+case,'source':'integer occupancy from saved jobs and 2976/480 capacity','pdf_total':re.findall(r'0\.\d{6}',totals)[int(case[1])-1],'weighted_exact':weighted,'occupancy_exact':from_seconds,'status':'PASS' if abs(weighted-from_seconds)<1e-14 else 'FAIL'})
    for name,actual,expected in [('own',own,expected_own),('contribution',contrib,expected_contrib),('total',totals,expected_totals)]:record('allocation.pdf.'+name,re.findall(r'0\.\d{6}',actual),expected,'saved_timing_checks integer occupancy by C1-C4')
    statement='For both FCFS and SPT-HOL, Hash-10% achieves lower mean A10 JCT at σ = 1, whereas Shape-filtered achieves lower mean A10 JCT at σ = 2. Shape-filtered also has the smaller worst-case value across these two evaluated scenarios.'
    for target,txt in [('abstract',pages[0]),('Q3',text[text.index('Table 5: Fixed-split results: (b)'):])]:
        clean=re.sub(r'\s+',' ',txt).replace('- filtered','-filtered')
        record('winners.sentence.'+target,statement in clean,True,'same policy/cohort/sigma formal comparisons + two-point maxima')
    sentence=re.search(r'The per-scenario FCFS A10 means are (.*?)These are evaluated points',flat).group(1)
    h=generated['winners']['FCFS'];s=generated['winners']['SPT-HOL']
    expected=[f"{h['1'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]+[f"{h['2'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]+[f"{s['1'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]+[f"{s['2'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]+[f"{h['two_point_max'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]+[f"{s['two_point_max'][o]:.3f}" for o in ['Hash-10%','Shape-filtered']]
    record('winners.pdf_numbers',re.findall(r'\d+\.\d{3}',sentence),expected,'main_table.csv FCFS/A10; C1-C4 original_A10.mean_jct_hours')
    ratio=re.search(r'ordinary mean is ([\d.]+) times higher',flat).group(1)
    record('FCFS.mean_ratio',ratio,f"{r2['q2_a10_three_policy']['FCFS_B1']['mean_wait_h']/r2['q2_a10_three_policy']['SPT-HOL_C0']['mean_wait_h']:.2f}",'exact means; display rounding')
    record('abstract.wait_values',re.search(r'waiting from ([\d.]+) to ([\d.]+)',flat).groups(),tuple(f"{runtime[c]['metrics']['cohorts']['original_A10']['mean_wait_hours']:.3f}" for c in ['C0','C1']),'formal C0/C1 original_A10.mean_wait_hours',1)
    for member in ['SHI U Hou','Ziyao Zhang','Beichen Ji','Sirui Zheng','HKUST(GZ)','Team falcons']:record('identity.'+member,member in pages[0],True,'confirmed user messages',1)
    record('AI.at_end','Use of AI Tools' in pages[-1] and all(n in pages[-1] for n in ['ChatGPT','OpenAI Codex','Claude']),True,'AI section is final section',len(doc))
    forbidden=['full-C1','C0','C1','C2','C3','C4','BOM','ZIP','LOCAL_ONLY','TEAM TO CONFIRM','TODO','/home/','results/','commit','deferred','??']
    record('body.no_internal_metadata',[t for t in forbidden if t in text],[],'reader-facing publication')
    fonts=[];exceptions=[];bad=[];outside=[]
    for i,pg in enumerate(doc):
        for b in pg.get_text('dict')['blocks']:
            for l in b.get('lines',[]):
                for s in l['spans']:
                    if not s['text'].strip():continue
                    entry={'page':i+1,'text':s['text'],'font':s['font'],'size_pdf_pt':s['size'],'bbox':s['bbox']}
                    if s['size']<11:
                        # Only CM math script fonts. Figure axis labels are never exempt.
                        if re.match(r'CM(?:MI|R|SY)[568]$',s['font']) and s['size']<9:exceptions.append(entry)
                        else:bad.append(entry)
                    else:fonts.append(s['size'])
                    x0,y0,x1,y1=s['bbox']
                    if min(x0,y0)<0 or x1>pg.rect.width or y1>pg.rect.height:outside.append(entry)
    record('fonts.non_script_below_11',bad,[],'actual embedded text spans; scripts enumerated separately')
    record('layout.text_outside_page',outside,[],'actual PDF text bounding boxes')
    record('format.max_10_pages',len(doc)<=10,True,'all pages counted')
    record('format.A4',all(abs(pg.rect.width-595.276)<.05 and abs(pg.rect.height-841.89)<.05 for pg in doc),True,'actual MediaBox')
    report={'pdf_sha256':hashlib.sha256(a.pdf.read_bytes()).hexdigest(),'pages':len(doc),'checks':checks,'minimum_ordinary_font_pdf_pt':min(fonts),'math_script_exceptions':exceptions,'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','visual_review':'SEPARATE_REQUIRED','human_review':'NOT_RUN'}
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    a.out.with_suffix('.txt').write_text(text)
    print(json.dumps({'status':report['status'],'checks':len(checks),'failed':[c['item'] for c in checks if c['status']!='PASS'],'pages':len(doc),'minimum_ordinary_pdf_pt':min(fonts)}))
    raise SystemExit(0 if report['status']=='PASS' else 1)
if __name__=='__main__':main()
