#!/usr/bin/env python3
"""Assemble an allow-listed standalone supplement without raw data or ledgers."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[2]
PROBLEM=Path('problems/2026_gpu_scheduling')
PUB=PROBLEM/'paper/final_publication'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def portable(s):
    return re.sub(r'/home/shiuhou/mm/([^/\s"\\]+)',r'LOCAL_ONLY/\1',s).replace('/home/shiuhou/','LOCAL_ONLY/')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('Do not overwrite an existing package')
    copied={}
    with tempfile.TemporaryDirectory(prefix='final-package-') as tmp:
        stage=Path(tmp)
        def copy(rel,dest=None,redact=False):
            src=ROOT/rel;dest=Path(dest or rel);assert src.is_file() and not src.is_symlink(),src
            target=stage/dest;target.parent.mkdir(parents=True,exist_ok=True)
            if redact:target.write_text(portable(src.read_text()))
            else:shutil.copyfile(src,target)
            copied[str(dest)]={'repository_source':str(rel),'source_sha256':sha(src),'package_sha256':sha(target),'transformation':'portable provenance prefixes only' if redact and sha(src)!=sha(target) else 'unchanged'}
        for f in (ROOT/PROBLEM/'src').rglob('*.py'):copy(f.relative_to(ROOT))
        for name in ['test_baseline.py','test_gang_placement.py','test_q3.py','test_q3_v2_shape.py','test_q2_bounds.py']:copy(PROBLEM/'tests'/name)
        for name in ['eda_analysis.py','generate_figures.py','analyze_m2f_bounds.py','verify_q3_fixed_split.py']:copy(PROBLEM/'experiments'/name)
        for f in (ROOT/PROBLEM/'configs').glob('*.json'):copy(f.relative_to(ROOT))
        copy(PROBLEM/'requirements.txt','requirements.txt')
        for f in (ROOT/PUB/'supplement').iterdir():
            if f.is_file():copy(f.relative_to(ROOT),f.name)
        for f in (ROOT/PUB).rglob('*'):
            if not f.is_file() or 'supplement' in f.relative_to(ROOT/PUB).parts or '__pycache__' in f.parts:continue
            if f.suffix in ['.py','.tex','.json','.pdf','.csv']:copy(f.relative_to(ROOT))
        dirs=['20261014-b-q1-intake-4a8f8f2b','20261015-b-q1-capacity-bound','20261015-b-q2-m2f-01','20261015-b-q3-fixed-split-c9e8f1a2','20261015-b-q3-s2-fixed-split-v1','20261018-b-q3-v2-r1-6f2c8a10','20261018-b-gs1-placement-v2-r1','20261018-b-q2-v2-r1-01','20261019-paper-content-r1','20261019-paper-content-r2']
        for d in dirs:
            for f in (ROOT/'results'/d).rglob('*'):
                if f.is_file() and f.suffix in ['.json','.csv','.md'] and f.stat().st_size<2_000_000:copy(f.relative_to(ROOT),redact=True)
        for rel in ['results/20261019-b-v2-integration-candidate/v2_runtime_equivalence.json','results/20261019-b-v2-integration-candidate/q2_persisted_replay.json','results/20261020-final-publication/saved_timing_checks.json']:
            copy(Path(rel),redact=True)
        # Regenerate only the source hash map for portable evidence copies; table bytes
        # must remain identical to the publication. No formal artifact is overwritten.
        spec=importlib.util.spec_from_file_location('portable_gen',stage/PUB/'generate.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        mod.generate(stage,stage/PUB/'generated')
        for f in (stage/PUB/'generated').glob('*'):
            if f.name.endswith('.tex'):assert f.read_bytes()==(ROOT/PUB/'generated'/f.name).read_bytes()
            key=str(f.relative_to(stage))
            if key in copied and copied[key]['package_sha256']!=sha(f):
                copied[key]['package_sha256']=sha(f);copied[key]['transformation']='same numeric values; digests regenerated for portable evidence copies'
        manifest={'core_commit':'990846fc89bf714d8e88e458d028d1f0d22712a4','publication_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'publication_identity':'exact included source hashes; source commit above; artifact commit recorded in handoff','files':copied,'excluded':['raw CSV','large timings and node ledgers','Git metadata','virtual environments','caches','credentials','standalone font files','third-party official documents'],'full_matrix_this_task':'NOT_RUN','source_mutations':'none in scheduling core; optional resource telemetry in analysis tool; portable wrappers and publication I/O only'}
        (stage/'package_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        # Static packaging safety and independence checks.
        for f in stage.rglob('*'):
            assert not f.is_symlink()
            assert f.name not in ['.git','.venv','__pycache__','node_info_df.csv','job_info_clean.csv']
            if f.suffix in ['.py','.md','.json','.txt']:
                content=f.read_text();assert '/home/shiuhou/' not in content,f
                assert not re.search(r'-----BEGIN .*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}',content),f
        a.out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for f in sorted(stage.rglob('*')):
                if not f.is_file():continue
                info=zipfile.ZipInfo(str(f.relative_to(stage)),date_time=(2026,10,20,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o644)<<16
                z.writestr(info,f.read_bytes())
        assert a.out.stat().st_size<=50_000_000
        print(json.dumps({'file':str(a.out),'bytes':a.out.stat().st_size,'sha256':sha(a.out),'members':len(zipfile.ZipFile(a.out).namelist())}))
if __name__=='__main__':main()
