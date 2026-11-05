"""Start the local preview without changing Windows script policy."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:12393/cyrene-preview.html'
MODEL = 'http://127.0.0.1:12393/live2d-models/cyrene/cyrene.model3.json'


def ready():
    try:
        with urllib.request.urlopen(MODEL, timeout=1) as response:
            data = json.load(response)
            return data['FileReferences']['Moc'] == 'cyrene.moc3'
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not ready():
        logs = ROOT / 'logs'
        logs.mkdir(exist_ok=True)
        env = os.environ.copy()
        env['PATH'] = str(ROOT / 'tools' / 'ffmpeg') + os.pathsep + env.get('PATH', '')
        env['PYTHONUTF8'] = '1'
        with (logs / 'server.stdout.log').open('ab') as stdout, (logs / 'server.stderr.log').open('ab') as stderr:
            process = subprocess.Popen([str(ROOT / '.venv' / 'Scripts' / 'python.exe'), 'run_server.py'],
                                       cwd=ROOT, env=env, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
                                       creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
        (ROOT / 'preview-server.pid').write_text(str(process.pid), 'ascii')
        for attempt in range(60):
            time.sleep(1)
            if ready():
                break
            if process.poll() is not None:
                raise SystemExit('Backend exited. Check logs/server.stderr.log.')
        else:
            raise SystemExit('Backend is not ready. Check logs/server.stderr.log.')
    print('Cyrene preview: ' + URL)
    if not args.no_browser:
        webbrowser.open(URL)


if __name__ == '__main__':
    main()
