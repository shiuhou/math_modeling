"""Delivery must work without a handoff ZIP and reject corrupted evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROBLEM=Path(__file__).resolve().parents[1]
REPO=PROBLEM.parents[1]
REFERENCE=REPO/'results/20261014-b-q1-intake-4a8f8f2b'


class DeliveryChecks(unittest.TestCase):
    def test_git_reference_and_numeric_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);result=root/'results';result.mkdir()
            for p in REFERENCE.iterdir():
                if p.suffix=='.csv' or p.name=='q1_results.json':shutil.copyfile(p,result/p.name)
            command=[sys.executable,str(PROBLEM/'experiments/verify_q1.py'),'--reference-dir',str(REFERENCE),'--results',str(result)]
            output=root/'verified.json'
            passed=subprocess.run([*command,'--out',str(output)],capture_output=True,text=True)
            self.assertEqual(passed.returncode,0,passed.stderr)
            self.assertEqual(json.loads(output.read_text())['input_provenance']['historical_job_byte_identity'],'BLOCKED')
            csv=result/'immediate_start_demand.csv';csv.write_text(csv.read_text(encoding='utf-8-sig').replace('3614.54040431','3664.0'),encoding='utf-8-sig')
            failed=subprocess.run([*command,'--out',str(root/'bad.json')],capture_output=True,text=True)
            self.assertNotEqual(failed.returncode,0)
            self.assertFalse((root/'bad.json').exists())

    def test_missing_compiler_reports_blocked_without_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'build'
            result=subprocess.run([sys.executable,str(PROBLEM/'experiments/build_paper.py'),'--scope','q1',
                '--compiler',str(Path(temp)/'no-such-compiler'),'--out',str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('BLOCKED',result.stderr)
            self.assertFalse(out.exists())
