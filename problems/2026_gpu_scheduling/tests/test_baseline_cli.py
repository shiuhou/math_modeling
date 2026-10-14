"""Round-trip the real CLI and reject corrupted persisted capacity evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import pandas as pd

PROBLEM=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROBLEM/'experiments'))
from verify_baseline import verify


class BaselineCLI(unittest.TestCase):
    def test_saved_ledger_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as task_dir:
            base=Path(task_dir)
            data=base/'data';data.mkdir()
            pd.DataFrame({'node_name':[0],'gpu_model':['X'],'gpu_capacity_num':[1],'cpu_num':[1]}).to_csv(data/'node_info_df.csv',index=False)
            pd.DataFrame({'job_name':[0,1],'gpu_model':['X','X'],'gpu_request':[1,1],'cpu_request':[.6,.6],'worker_num':[1,1],'submit_time':[0,1],'duration':[2,2]}).to_csv(data/'job_info_clean.csv',index=False)
            run=base/'run'
            command=[sys.executable,str(PROBLEM/'experiments/run_baselines.py'),'--data',str(data),'--out',str(run)]
            subprocess.run(command,check=True,capture_output=True)
            self.assertEqual(verify(data,run)['status'],'PASS')
            refusal=subprocess.run(command,capture_output=True)
            self.assertNotEqual(refusal.returncode,0)
            # Change a placement and update its file hash to reach the independent
            # constraint check, rather than testing only the hash guard.
            path=run/'FCFS_node_placements.csv.gz'
            ledger=pd.read_csv(path);ledger.loc[0,'workers']=2
            ledger.to_csv(path,index=False,compression='gzip')
            meta=json.loads((run/'run.json').read_text())
            meta['outputs'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (run/'run.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(AssertionError,'Worker count'):
                verify(data,run)
