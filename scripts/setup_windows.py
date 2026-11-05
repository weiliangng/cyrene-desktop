"""Restore local runtime dependencies and compile the private Windows desktop client."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'Open-LLM-VTuber'
DESKTOP = ROOT / 'Open-LLM-VTuber-Web'

def run(args, cwd=ROOT):
    print('Running:', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--skip-desktop-build',action='store_true')
    parser.add_argument('--with-openclaw',action='store_true')
    parser.add_argument('--uv-cache',type=Path,default=ROOT/'tmp/uv-cache')
    parser.add_argument('--npm-cache',type=Path,default=ROOT/'tmp/npm-cache')
    args=parser.parse_args()
    args.uv_cache=args.uv_cache.resolve()
    args.npm_cache=args.npm_cache.resolve()
    uv=shutil.which('uv')
    npm=shutil.which('npm.cmd') or shutil.which('npm')
    if not uv or not npm:
        raise SystemExit('Install uv and Node.js/npm first, then run Setup Cyrene.cmd again.')
    for target,template in [('conf.yaml','conf.cyrene.yaml'),('mcp_servers.json','mcp_servers.example.json')]:
        if not (BACKEND/target).exists():
            shutil.copy2(BACKEND/template,BACKEND/target)
    run([uv,'sync','--frozen','--python','3.12','--cache-dir',args.uv_cache],BACKEND)
    python=BACKEND/'.venv/Scripts/python.exe'
    ffmpeg=BACKEND/'tools/ffmpeg/ffmpeg.exe'
    if not ffmpeg.exists():
        run([uv,'pip','install','--python',python,'--cache-dir',args.uv_cache,'imageio-ffmpeg==0.6.0'],BACKEND)
        binary=subprocess.check_output([python,'-c','import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],text=True).strip()
        ffmpeg.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(binary,ffmpeg)
    manifest=json.loads((ROOT/'runtime-downloads.json').read_text(encoding='utf-8'))
    model=BACKEND/manifest['asr']['model']
    if not model.exists():
        archive=ROOT/'tmp/sense-voice.tar.bz2'
        archive.parent.mkdir(parents=True,exist_ok=True)
        print('Downloading the bundled speech-recognition model...',flush=True)
        urllib.request.urlretrieve(manifest['asr']['url'],archive)
        (BACKEND/'models').mkdir(exist_ok=True)
        with tarfile.open(archive) as source:
            source.extractall(BACKEND/'models',filter='data')
    if hashlib.sha256(model.read_bytes()).hexdigest()!=manifest['asr']['sha256']:
        raise SystemExit('Speech model hash mismatch; check the local model before launching.')
    if args.with_openclaw:
        run([npm,'ci','--omit=optional','--cache',args.npm_cache,'--maxsockets=2','--no-audit','--no-fund'],ROOT/'integrations/openclaw')
        run([python,ROOT/'scripts/setup_openclaw.py','configure','--connect'])
    if not args.skip_desktop_build:
        run([npm,'ci','--cache',args.npm_cache,'--no-audit','--no-fund'],DESKTOP)
        run([npm,'run','build'],DESKTOP)
        run([npm,'run','package:local'],DESKTOP)
    print('Ready. Launch Start Cyrene Desktop.cmd.',flush=True)

if __name__=='__main__':
    main()
