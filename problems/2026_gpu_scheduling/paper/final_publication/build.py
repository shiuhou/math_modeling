#!/usr/bin/env python3
"""Build the one publication entry in a new directory; never overwrite a PDF."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--compiler',default='tectonic')
    a=p.parse_args();a.out=a.out.resolve()
    if a.out.exists():p.error('Choose a new output directory')
    source=Path(__file__).resolve().parent
    subprocess.run([sys.executable,str(source/'generate.py')],check=True)
    a.out.mkdir(parents=True)
    for f in source.glob('*.tex'):shutil.copyfile(f,a.out/f.name)
    for sub in ['generated','figures']:shutil.copytree(source/sub,a.out/sub)
    cmd=[a.compiler,'--keep-logs','--keep-intermediates','document.tex']
    run=subprocess.run(cmd,cwd=a.out,text=True,capture_output=True)
    (a.out/'compiler.log').write_text(run.stdout+run.stderr)
    run.check_returncode()
    pdf=a.out/'document.pdf'
    sources={str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(source.rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
    (a.out/'build_record.json').write_text(json.dumps({'entry':'document.tex','sources_sha256':sources,'command':['tectonic','--keep-logs','--keep-intermediates','document.tex'],'exit_code':run.returncode,'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},indent=2)+'\n')
    print(pdf)
if __name__=='__main__':main()
