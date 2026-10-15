"""One-time evidence assembly, run after all bounded children terminate."""
import hashlib,json,subprocess,tarfile
from pathlib import Path
root=Path('results/20261015-b-q2-m2e-01')
paths=[Path('outputs/q2-m2e-recovery-65536-time-20261015'),Path('outputs/q2-m2e-recovery-65536-remaining-20261015')]
combined=Path('outputs/q2-m2e-recovery-65536-combined-20261015')
combined.mkdir(exist_ok=False)
records=[]
for directory in paths:
 b=json.loads((directory/'benchmark.json').read_text())
 for r in b['records']:
  if r.get('status','PASS')=='PASS':
   child=directory/r['child_output']; dest=root/(child.name+'-verified.json')
   if not dest.exists():
    subprocess.run(['.venv/bin/python','problems/2026_gpu_scheduling/experiments/verify_m2a_pressure.py','--run',str(child),'--out',str(dest)],check=True)
   assert json.loads(dest.read_text())['status']=='PASS'
   r['child_output']='../'+directory.name+'/'+child.name
  records.append(r)
 config=b['configuration']
 (root/('benchmark-65536-'+('time' if len(b['records'])==1 else 'remaining')+'.json')).write_bytes((directory/'benchmark.json').read_bytes())
config['policies']=[r['policy'] for r in records]
joined={'kind':'m2e_joined_original_benchmark_records','status':'PASS' if all(r.get('status','PASS')=='PASS' for r in records) else 'INCOMPLETE','configuration':config,'records':records,'original_benchmarks':[str(d/'benchmark.json') for d in paths]}
(combined/'benchmark.json').write_text(json.dumps(joined,indent=2)+'\n')
subprocess.run(['.venv/bin/python','problems/2026_gpu_scheduling/experiments/analyze_m2e.py','--benchmark',str(combined),'--verification-dir',str(root),'--out',str(root/'comparison-65536.json')],check=True)
subprocess.run(['.venv/bin/python','problems/2026_gpu_scheduling/experiments/analyze_m2d_pairs.py','--benchmark',str(combined),'--out',str(root/'pairs-65536.json')],check=True)
archive=root/'evidence-65536.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz',compresslevel=6) as t:
 for p in paths+[combined]: t.add(p,arcname=str(p))
with tarfile.open(archive) as t:
 for m in t.getmembers():
  if m.isfile():
   assert hashlib.sha256(t.extractfile(m).read()).digest()==hashlib.sha256(Path(m.name).read_bytes()).digest(),m.name
archives=json.loads((root/'archives.json').read_text())
archives.append({'path':archive.name,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive_member_byte_check':'PASS'})
(root/'archives.json').write_text(json.dumps(archives,indent=2)+'\n')
print('Evidence assembled')
