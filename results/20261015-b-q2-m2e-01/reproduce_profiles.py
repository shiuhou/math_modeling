import argparse,json,subprocess,time
from pathlib import Path
import sys
sys.path.insert(0,'problems/2026_gpu_scheduling/experiments')
from run_m2b_benchmark import process_rss_kib
parser=argparse.ArgumentParser(description='Sequential bounded M2-E profiles; choose a NEW evidence directory.')
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
if args.out.exists(): parser.error('output exists')
root=args.out
root.mkdir(parents=True)
specs=[(8192,4,p,rev) for p in ['SPT-URGENT-TIME','SPT-URGENT-FIXED','SPT-URGENT-FLEX'] for rev in ['8da62ad',None]]
specs += [(32768,604800,'SPT-URGENT-TIME','8da62ad'),(32768,604800,'SPT-URGENT-FLEX',None)]
records=[]
for jobs,theta,policy,rev in specs:
 out=root/f'profile-{jobs}-{theta}-{policy}-{rev or "optimized"}.json'
 command=['.venv/bin/python','problems/2026_gpu_scheduling/experiments/profile_m2e.py','--jobs',str(jobs),'--theta-seconds',str(theta),'--policy',policy,'--out',str(out)]
 if rev: command+=['--revision',rev]
 start=time.perf_counter();child=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
 peak=0;status='PASS'
 while child.poll() is None:
  rss=process_rss_kib(child.pid) or 0;peak=max(peak,rss)
  if rss>4194304 or time.perf_counter()-start>900:
   status='RSS_LIMIT' if rss>4194304 else 'TIMEOUT';child.kill();break
  time.sleep(.1)
 _,err=child.communicate()
 if child.returncode and status=='PASS':status='FAIL'
 records.append(dict(command=command,status=status,elapsed_seconds=time.perf_counter()-start,observed_peak_rss_kib=peak,stderr=err,out=str(out)))
 (root/'profile-batch.json').write_text(json.dumps(records,indent=2)+'\n')
 print(out,status,flush=True)
