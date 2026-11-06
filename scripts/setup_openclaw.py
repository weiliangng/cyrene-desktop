"""Project-local OpenClaw profile; no global config or Windows service changes."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request
from startup_lock import startup_lock
from gateway_startup import gateway_status, wait_for_gateway

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / 'integrations/openclaw'
STATE = ROOT / 'tmp/openclaw'
CONFIG = STATE / 'openclaw.json'
CLI = INTEGRATION / 'node_modules/openclaw/openclaw.mjs'

def environment():
    env = os.environ.copy()
    env['OPENCLAW_STATE_DIR'] = str(STATE)
    env['OPENCLAW_CONFIG_PATH'] = str(CONFIG)
    env['NODE_OPTIONS'] = '--max-old-space-size=1536'
    env.pop('ELECTRON_RUN_AS_NODE', None)
    return env

def configure(connect=False):
    STATE.mkdir(parents=True, exist_ok=True)
    if not CLI.exists():
        raise SystemExit('Install the pinned runtime first: npm.cmd ci --prefix integrations/openclaw --omit=optional --no-audit --no-fund')
    token_file = STATE / 'gateway-token'
    if not token_file.exists(): token_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
    token = token_file.read_text(encoding='utf-8').strip()
    workspace = STATE / 'workspace'
    workspace.mkdir(exist_ok=True)
    for template in (INTEGRATION / 'workspace').glob('*.md'):
        target = workspace / template.name
        if not target.exists(): target.write_bytes(template.read_bytes())
    # Generate only once, preserving later plugin/model customizations.
    if not CONFIG.exists():
        config = {
            'gateway': {'mode':'local', 'bind':'loopback', 'port':18789,
                'auth': {'mode':'token','token':token},
                'http': {'endpoints': {'chatCompletions': {'enabled': True}}}},
            'models': {'mode':'merge','providers': {'soclaas': {
                'baseUrl':'https://soclaas-api.comp.nus.edu.sg/v1', 'apiKey':'${SOCLAAS_API_KEY}',
                'api':'openai-completions','authHeader':True,
                'models':[{'id':'qwen3.8:27b','name':'SoCLaaS Qwen 3.8 27B','reasoning':False,
                    'input':['text'],'contextWindow':131072,'maxTokens':8192,
                    'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0}}]}}},
            'agents': {'defaults': {'workspace':str(workspace),
                'model':{'primary':'soclaas/qwen3.8:27b'}, 'thinkingDefault':'off',
                'heartbeat':{'every':'0m'}, 'maxConcurrent':1},
                'entries':{'cyrene':{'name':'Cyrene'}}},
            'plugins': {'allow':['cyrene'], 'load':{'paths':[str(INTEGRATION / 'cyrene-plugin')]},
                'entries':{'cyrene': {'enabled':True,'hooks':{'allowConversationAccess':True},
                    'config':{'baseUrl':'http://127.0.0.1:12393/api/cyrene',
                        'tokenFile':str(ROOT / 'tmp/cyrene-control/token'),'agentId':'cyrene'}}}},
            'tools': {'profile':'full'},
        }
        CONFIG.write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    if connect:
        from ruamel.yaml import YAML
        yaml = YAML()
        conf_path = ROOT / 'Open-LLM-VTuber/conf.yaml'
        backup = STATE / 'conf.before-openclaw.yaml'
        if not backup.exists(): backup.write_bytes(conf_path.read_bytes())
        conf = yaml.load(conf_path)
        conf['system_config']['ui_only'] = True
        agent = conf['character_config']['agent_config']
        agent['agent_settings']['basic_memory_agent']['llm_provider'] = 'openai_compatible_llm'
        agent['agent_settings']['basic_memory_agent']['use_mcpp'] = False
        config = agent['llm_configs']['openai_compatible_llm']
        config.update({'base_url':'http://127.0.0.1:18789/v1','llm_api_key':token,
            'model':'openclaw/cyrene','request_user':'cyrene-desktop', 'temperature':0.7})
        with conf_path.open('w', encoding='utf-8') as stream: yaml.dump(conf, stream)
    return token

def ready(token):
    return gateway_status(token)[0] == 'ready'

def start(connect=False):
    with startup_lock(STATE / 'launch.lock'):
        token = configure(connect)
        def spawn():
            if not os.environ.get('SOCLAAS_API_KEY'):
                raise SystemExit('SOCLAAS_API_KEY is missing from the launch environment. Set it and reopen the launcher.')
            with (STATE / 'gateway.stdout.log').open('ab') as stdout, (STATE / 'gateway.stderr.log').open('ab') as stderr:
                marker = ('\n--- Cyrene launcher: ' + time.strftime('%Y-%m-%d %H:%M:%S') + ' ---\n').encode()
                stderr.write(marker); stderr.flush()
                process = subprocess.Popen(['node',str(CLI),'gateway','run'], cwd=ROOT, env=environment(),
                    stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
            (STATE / 'gateway.pid').write_text(str(process.pid), encoding='ascii')
            return process
        try:
            wait_for_gateway(token, CLI, spawn)
        except RuntimeError as error:
            raise SystemExit(str(error)) from None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['configure','start','cli'])
    parser.add_argument('--connect', action='store_true', help='Route desktop chat through OpenClaw; back up current local config')
    args, rest = parser.parse_known_args()
    if args.action == 'start':
        start(args.connect)
        return
    with startup_lock(STATE / 'launch.lock'):
        configure(args.connect)
    if args.action == 'cli':
        raise SystemExit(subprocess.call(['node',str(CLI),*rest], cwd=ROOT, env=environment()))
    else: print('Project OpenClaw profile configured. Runtime settings stay in tmp/openclaw.')

if __name__ == '__main__': main()
