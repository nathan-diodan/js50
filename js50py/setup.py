from js50py import config
from js50py.animation_helper.sticker_pack_cache import StickerCollector
import subprocess
import json

print('JS50 lamp setup')
print('create needed folder')

for folder in [config.fonts_folder, config.telegram_sticker_folder, config.telegram_video_folder]:
    folder.mkdir(exist_ok=True, parents=True)

print('Setup Telegram Bot')
if not config.settings.is_file():
    print('Telegram settings')
    tel_token = input('token: ').strip()
    secret = input('new user secret: ').strip()
    settings_data = dict(
        token=tel_token,
        secret=secret,
        user=[],
        admin=[],
        blacklist=[]
    )
    config.settings.write_text(json.dumps(settings_data, indent=4))

print('prepare telegram sticker converter')

if not (config.tgs_tool_folder / 'node_modules').is_dir():
    subprocess.run(['npm', 'install'], cwd=config.tgs_tool_folder)

print('fill cache')
pyrogram_config = config.base_dir / 'js50py' / 'animation_helper' / 'pyrogram.ini'
if not pyrogram_config.is_file():
    print('pyrogram settings:')
    api_id = input('api_id')
    api_hash = input('api_hash')
    pyrogram_config.write_text(f"[pyrogram]\napi_id = {api_id}\napi_hash = {api_hash}")

sc = StickerCollector(config_file=pyrogram_config)
base_sticker = sc.get_set_emojis_dict(None)
print(f"Cached {len(base_sticker)} Telegram animations")
sc.client.stop()
del sc

