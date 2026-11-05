"""Authenticated local CLI; also importable by automation and the MCP adapter."""
import argparse
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:12393/api/cyrene'

def request(path, body=None, timeout=35):
    token = (ROOT / 'tmp/cyrene-control/token').read_text(encoding='utf-8').strip()
    data = None if body is None else json.dumps(body).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('state')
    send = sub.add_parser('send')
    send.add_argument('name')
    send.add_argument('--data', default='{}', help='JSON object; use --file for complex data on Windows')
    send.add_argument('--file', type=Path)
    send.add_argument('--request-id')
    watch = sub.add_parser('watch')
    watch.add_argument('--after', type=int, default=0)
    args = parser.parse_args()
    if args.action == 'state':
        print(json.dumps(request('/state'), ensure_ascii=True, indent=2))
    elif args.action == 'send':
        data = json.loads(args.file.read_text(encoding='utf-8-sig') if args.file else args.data)
        print(json.dumps(request('/commands', {'name': args.name, 'data': data, 'request_id': args.request_id, 'source': 'cli'})))
    else:
        cursor = args.after
        try:
            while True:
                batch = request(f'/events?after={cursor}&wait=25')
                if batch['gap']: print(json.dumps({'type': 'events.gap', 'oldest_id': batch['oldest_id']}), flush=True)
                for event in batch['events']: print(json.dumps(event, ensure_ascii=True), flush=True)
                cursor = batch['cursor']
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
