"""Optional, foreground download notifications. No file contents are read."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2] / 'scripts'))
from cyrene_control import request

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path.home() / 'Downloads')
    parser.add_argument('--invoke-agent', action='store_true', help='Explicitly ask OpenClaw to react; otherwise emit an event only')
    args = parser.parse_args()
    folder = args.path.resolve(strict=True)
    if not folder.is_dir(): raise SystemExit('The download path must be a directory')
    def scan():
        files = {}
        for path in folder.iterdir():
            try:
                if path.is_file():
                    stat = path.stat()
                    files[path] = (stat.st_size, stat.st_mtime_ns)
            except OSError: pass
        return files
    seen = scan()
    candidates = {}
    notified = dict(seen)
    print(f'Watching {folder}. Existing files are ignored. Ctrl+C stops.', flush=True)
    try:
        while True:
            time.sleep(2)
            now = time.monotonic()
            current = scan()
            for path, signature in current.items():
                if path.suffix.lower() in ('.crdownload','.part','.partial','.tmp') or notified.get(path) == signature: continue
                previous = candidates.get(path)
                if previous is None or previous[0] != signature:
                    candidates[path] = (signature, now)
                elif now - previous[1] >= 6:
                    try:
                        request('/commands', {'name':'input.event','source':'download-watcher','data':{
                            'event':'download.completed','payload':{'path':str(path),'name':path.name,'bytes':signature[0]},
                            'invoke_agent':args.invoke_agent}})
                        print(f'Emitted download.completed: {path.name}', flush=True)
                        notified[path] = signature
                    except Exception as error: print(f'Notification failed: {error}', flush=True)
            for path in list(candidates):
                if path not in current: candidates.pop(path,None)
            for path in list(notified):
                if path not in current: notified.pop(path,None)
    except KeyboardInterrupt: pass

if __name__ == '__main__': main()
