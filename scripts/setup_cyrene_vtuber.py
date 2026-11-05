from pathlib import Path, PurePosixPath
import json
import shutil
import zipfile
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'Open-LLM-VTuber'
archive = Path.home() / 'Downloads' / '昔涟VTS.zip'
dest = APP / 'live2d-models' / 'cyrene'
dest.mkdir(parents=True, exist_ok=True)
aliases = {'吐舌': 'playful', '哭': 'cry', '头纱': 'veil', '委屈': 'hurt',
           '星星': 'star_eyes', '水': 'watermark', '流汗': 'sweat', '生气': 'angry',
           '睡觉': 'sleep', '笑': 'happy', '脸红': 'blush', '迷迷': 'mimi',
           '问号': 'confused', 'VTS气泡': 'key_bubbles'}
expressions = []
with zipfile.ZipFile(archive) as source:
    if source.testzip():
        raise ValueError('Invalid model ZIP')
    prefix = '昔涟VTS/'
    for entry in source.infolist():
        if entry.is_dir() or not entry.filename.startswith(prefix):
            continue
        relative = entry.filename[len(prefix):].replace('昔涟VTS', 'cyrene').replace('昔涟.png', 'cyrene.png')
        if relative.endswith('.exp3.json'):
            stem = relative[:-len('.exp3.json')]
            relative = aliases.get(stem, stem) + '.exp3.json'
            expressions.append({'Name': relative[:-len('.exp3.json')], 'File': relative})
        target = (dest / relative).resolve()
        if not target.is_relative_to(dest.resolve()):
            raise ValueError('Unsafe ZIP path')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read(entry))
model_path = dest / 'cyrene.model3.json'
model = json.loads(model_path.read_text('utf-8'))
model['FileReferences'] = {key: ([s.replace('昔涟VTS', 'cyrene') for s in val] if isinstance(val, list)
                                else val.replace('昔涟VTS', 'cyrene'))
                           for key, val in model['FileReferences'].items()}
neutral_ids = set()
facial_names = ['angry', 'cry', 'happy', 'blush', 'playful', 'star_eyes', 'hurt', 'sleep', 'sweat', 'confused', 'wink']
for name in facial_names:
    data = json.loads((dest / (name + '.exp3.json')).read_text('utf-8'))
    neutral_ids.update(p['Id'] for p in data['Parameters'] if not p['Id'].startswith('ParamEye'))
neutral = {'Type': 'Live2D Expression', 'FadeInTime': 0.15, 'FadeOutTime': 0.15,
           'Parameters': [{'Id': name, 'Value': 0, 'Blend': 'Overwrite'} for name in sorted(neutral_ids)]}
(dest / 'neutral.exp3.json').write_text(json.dumps(neutral, indent=2), 'utf-8')
ordered = [{'Name': 'neutral', 'File': 'neutral.exp3.json'}]
ordered.extend(next(e for e in expressions if e['Name'] == name) for name in facial_names)
ordered.extend(e for e in expressions if e['Name'] not in facial_names)
model['FileReferences']['Expressions'] = ordered
model['FileReferences'].pop('Motions', None)
for expression_path in dest.glob('*.exp3.json'):
    expression = json.loads(expression_path.read_text('utf-8'))
    inactive_animation_ids = ('Param23', 'Param25', 'Param26', 'Param27', 'Param28')
    expression['Parameters'] = [p for p in expression['Parameters'] if p['Id'] not in ('Param24', *inactive_animation_ids)]
    expression['Parameters'].extend([
        {'Id': 'Param24', 'Value': 1, 'Blend': 'Overwrite'},
        *[{'Id': parameter, 'Value': -1, 'Blend': 'Overwrite'} for parameter in inactive_animation_ids],
    ])
    expression_path.write_text(json.dumps(expression, ensure_ascii=False, indent=2), 'utf-8')
for group in model['Groups']:
    if group['Name'] == 'LipSync':
        group['Ids'] = ['ParamMouthOpenY']
model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), 'utf-8')
registry_path = APP / 'model_dict.json'
registry = json.loads(registry_path.read_text('utf-8'))
registry = [entry for entry in registry if entry['name'] != 'cyrene']
registry.append({'name': 'cyrene', 'description': 'Cyrene chibi model supplied by the user; private local preview.',
                 'url': '/live2d-models/cyrene/cyrene.model3.json', 'kScale': 0.55,
                 'initialXshift': 0, 'initialYshift': 0, 'idleMotionGroupName': 'Idle',
                 'defaultEmotion': 'neutral',
                 'emotionMap': {'neutral': 'neutral', 'joy': 'happy', 'anger': 'angry', 'sadness': 'cry',
                                'shy': 'blush', 'playful': 'playful', 'excited': 'star_eyes',
                                'hurt': 'hurt', 'sleepy': 'sleep', 'nervous': 'sweat',
                                'surprise': 'confused', 'wink': 'wink'}, 'tapMotions': {}})
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), 'utf-8')
config_path = APP / 'conf.yaml'
backup = APP / 'conf.original.yaml'
if not backup.exists():
    shutil.copy2(config_path, backup)
yaml = YAML()
config = yaml.load(backup.read_text('utf-8'))
config['system_config']['host'] = '127.0.0.1'
character = config['character_config']
character.update({'conf_name': 'cyrene', 'conf_uid': 'cyrene_local_preview', 'live2d_model_name': 'cyrene',
                  'character_name': 'Cyrene', 'avatar': 'cyrene.png',
                  'persona_prompt': 'You are Cyrene, a warm and playful desktop companion. Respond in English.'})
settings = character['agent_config']['agent_settings']['basic_memory_agent']
settings['llm_provider'] = 'openai_compatible_llm'
settings['use_mcpp'] = False
settings['mcp_enabled_servers'] = []
character['agent_config']['llm_configs']['openai_compatible_llm']['model'] = 'preview-not-configured'
character['agent_config']['llm_configs']['openai_compatible_llm']['llm_api_key'] = 'preview-placeholder'
with config_path.open('w', encoding='utf-8') as output:
    yaml.dump(config, output)
shutil.copy2(dest / 'cyrene.png', APP / 'avatars' / 'cyrene.png')
preview_config = {'modelUrl': '/live2d-models/cyrene/cyrene.model3.json',
                  'expressions': ['neutral', *facial_names],
                  'keyParameters': {'tab': 'Param29', '1': 'Param30', '2': 'Param31', '3': 'Param32',
                                    '4': 'Param33', 'shift': 'Param34', 'q': 'Param35', 'w': 'Param36',
                                    'e': 'Param37', 'r': 'Param38', ' ': 'Param39', 'a': 'Param40',
                                    's': 'Param41', 'd': 'Param42', 'f': 'Param43'}}
(APP / 'frontend' / 'cyrene-preview-config.json').write_text(json.dumps(preview_config, indent=2), 'utf-8')
for ref in [model['FileReferences']['Moc'], *model['FileReferences']['Textures'],
            model['FileReferences']['Physics'], model['FileReferences']['DisplayInfo'],
            *[e['File'] for e in ordered], 'Live2d_motion1.motion3.json']:
    if not (dest / ref).is_file():
        raise ValueError('Missing model asset: ' + ref)
print('Cyrene imported: 33 registered expressions, 11 facial presets + neutral, 3 textures; watermark hidden and heart motion disabled.')
