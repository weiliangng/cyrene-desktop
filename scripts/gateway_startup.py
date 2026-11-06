"""Observe and reuse a project gateway while its saved sessions recover."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

GATEWAY_URL = 'http://127.0.0.1:18789'


def get_json(path, token=None):
    headers = {'Authorization': 'Bearer ' + token} if token else {}
    request = urllib.request.Request(GATEWAY_URL + path, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            try:
                body = json.load(response)
            except (ValueError, UnicodeError):
                body = {}
            return response.status, body if isinstance(body, dict) else {}
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read())
        except (ValueError, UnicodeError):
            body = {}
        return error.code, body if isinstance(body, dict) else {}
    except (OSError, ValueError):
        return None, {}


def gateway_status(token):
    health_code, health = get_json('/healthz')
    if health_code is None:
        return 'absent', 'Gateway listener is not available yet'
    if health_code != 200 or health.get('status') != 'live' or health.get('ok') is not True:
        return 'conflict', 'Port 18789 is occupied by a different service'
    models_code, models = get_json('/v1/models', token)
    if models_code in (401, 403):
        return 'conflict', 'The gateway on port 18789 rejects this project token; a different OpenClaw profile may be running'
    if models_code == 200 and not any(model.get('id') == 'openclaw/cyrene' for model in models.get('data', [])):
        return 'conflict', 'The gateway on port 18789 does not expose this project\'s Cyrene agent'
    ready_code, state = get_json('/readyz', token)
    if ready_code == 200 and state.get('ready') is True and models_code == 200:
        return 'ready', 'Gateway and Cyrene agent are ready'
    failing = state.get('failing', [])
    reason = ', '.join(str(item) for item in failing) or 'Recovering saved sessions and initializing the gateway'
    return 'starting', reason


def gateway_processes(cli):
    """Find the exact project CLI, never trust a PID left by a previous boot."""
    cli = str(Path(cli).resolve()).casefold()
    if os.name == 'nt':
        command = "Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                                    capture_output=True, text=True, timeout=12,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise RuntimeError('Cannot inspect existing OpenClaw processes; not starting a potentially conflicting copy')
            processes = json.loads(result.stdout.strip() or '[]')
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise RuntimeError('Cannot inspect existing OpenClaw processes; try the launcher again') from error
        if isinstance(processes, dict):
            processes = [processes]
        return [int(process['ProcessId']) for process in processes
                if cli in (process.get('CommandLine') or '').casefold()
                and 'gateway' in (process.get('CommandLine') or '').replace('"', '').split()
                and 'run' in (process.get('CommandLine') or '').replace('"', '').split()]
    matches = []
    for entry in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            command = entry.read_bytes().decode().replace('\0', ' ')
            if cli in command.casefold() and 'gateway' in command.split() and 'run' in command.split():
                matches.append(int(entry.parent.name))
        except (OSError, UnicodeError):
            pass
    return matches


def wait_for_gateway(token, cli, spawn, timeout=240):
    """Called under the launcher lock; no new process for a recovering gateway."""
    status, reason = gateway_status(token)
    if status == 'ready':
        return
    if status == 'conflict':
        raise SystemExit(reason)
    owners = gateway_processes(cli) if status == 'absent' else []
    process = None
    if status == 'absent' and not owners:
        print('Starting OpenClaw. After a reboot, saved-session recovery can take a few minutes...', flush=True)
        process = spawn()
    else:
        print('OpenClaw is already starting; waiting for saved-session recovery...', flush=True)
    deadline = time.monotonic() + timeout
    next_notice = time.monotonic() + 15
    exit_seen_at = None
    while time.monotonic() < deadline:
        status, reason = gateway_status(token)
        if status == 'ready':
            print('OpenClaw ready at http://127.0.0.1:18789 (Cyrene agent).', flush=True)
            return
        if status == 'conflict':
            raise SystemExit(reason)
        # OpenClaw can hand off to another process. A live/recovering listener
        # takes precedence over the lifetime of the launcher process we spawned.
        if process is not None and process.poll() is not None and status == 'absent':
            if exit_seen_at is None:
                exit_seen_at = time.monotonic()
            if time.monotonic() - exit_seen_at >= 5:
                if gateway_processes(cli):
                    process = None
                else:
                    raise SystemExit(f'OpenClaw exited (code {process.returncode}); see tmp/openclaw/gateway.stderr.log')
        if time.monotonic() >= next_notice:
            print('Waiting for OpenClaw: ' + reason, flush=True)
            next_notice = time.monotonic() + 15
        time.sleep(1)
    raise SystemExit('OpenClaw is still recovering after four minutes. Its process has been left running; '
                     'run the launcher again to keep waiting. See tmp/openclaw/gateway.stderr.log.')
