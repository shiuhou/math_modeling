#!/usr/bin/env python3
"""Exercise the reported Windows failure modes on a freshly extracted supplement.

Runs only packaged small tests and synthetic CLI fixtures, never the full trace.
This is a Linux-side failure-mode test, not a native Windows execution claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    with tempfile.TemporaryDirectory(prefix='problem-b-portability-') as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(args.zip) as archive:
            archive.extractall(root)
        manifest = json.loads((root/'package_manifest.json').read_text(encoding='utf-8'))
        for name, info in manifest['files'].items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest() == info['package_sha256'], name

        def run(label, command, expected_exit=0):
            result = subprocess.run([sys.executable, '-I', *command], cwd=root,
                                    capture_output=True, text=True, encoding='utf-8')
            (args.out/(label+'.log')).write_text(result.stdout+result.stderr, encoding='utf-8')
            ok = result.returncode == expected_exit
            records.append({'check': label, 'command': ['python', '-I', *command],
                            'expected_exit': expected_exit, 'actual_exit': result.returncode,
                            'status': 'PASS' if ok else 'FAIL', 'log': label+'.log'})

        run('evidence_lf', ['check_evidence.py'])
        tables = root/'problems/2026_gpu_scheduling/paper/final_publication/generated'
        originals = {p: p.read_bytes() for p in tables.glob('*.tex')}
        for path, data in originals.items():
            path.write_bytes(data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        run('evidence_crlf', ['check_evidence.py'])
        for path, data in originals.items():
            path.write_bytes(data)
        target = tables/'table5.tex'
        data = target.read_bytes()
        assert b'217,578' in data
        target.write_bytes(data.replace(b'217,578', b'217,579', 1))
        run('changed_value_rejected', ['check_evidence.py'], expected_exit=1)
        target.write_bytes(data)
        run('smoke_without_resource', ['-c', '''
import importlib.abc
import runpy
import sys
class NoResource(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'resource':
            raise ModuleNotFoundError("Simulated Windows: no resource module", name='resource')
sys.modules.pop('resource', None)
sys.meta_path.insert(0, NoResource())
runpy.run_path('smoke.py', run_name='__main__')
'''])
        run('cli_help', ['reproduce.py', '--help'])
    report = {'zip_sha256': hashlib.sha256(args.zip.read_bytes()).hexdigest(),
              'member_hashes': 'PASS', 'checks': records,
              'status': 'PASS' if all(r['status']=='PASS' for r in records) else 'FAIL',
              'host': sys.platform, 'native_windows_test': 'NOT_RUN',
              'scope': 'CRLF fixture, missing-resource import, small unit tests and synthetic CLI only',
              'full_trace_or_historical_replay': 'NOT_RUN'}
    (args.out/'checks.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'checks': [{k:r[k] for k in ['check','status','actual_exit']} for r in records]}))
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
