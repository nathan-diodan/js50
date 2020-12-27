import config
from animation_helper.sticker_pack_cache import StickerCollector
import subprocess
import json
import urllib.request
import zipfile

print('JS50 lamp setup')
print('create needed folder')

for folder in [config.fonts_folder, config.telegram_sticker_folder,
               config.telegram_video_folder]:
    folder.mkdir(exist_ok=True, parents=True)

print('Prepare fonts:')
print('  Courier Prime')
if not (config.fonts_folder / 'CourierPrime-Regular.ttf').is_file():
    print('    downloading ...')
    url = 'https://fonts.google.com/download?family=Courier%20Prime'
    urllib.request.urlretrieve(url, config.fonts_folder / 'Courier.zip')
    print('    unzipping ...')
    with zipfile.ZipFile(config.fonts_folder / 'Courier.zip', 'r') as zip_ref:
        zip_ref.extractall(config.fonts_folder)
    (config.fonts_folder / 'Courier.zip').unlink()

print('  OpenSans')
if not (config.fonts_folder / 'OpenSans-SemiBold.ttf').is_file():
    print('    downloading ...')
    url = 'https://fonts.google.com/download?family=Open%20Sans'
    urllib.request.urlretrieve(url, config.fonts_folder / 'OpenSans.zip')
    print('    unzipping ...')
    with zipfile.ZipFile(config.fonts_folder / 'OpenSans.zip', 'r') as zip_ref:
        zip_ref.extractall(config.fonts_folder)
    (config.fonts_folder / 'OpenSans.zip').unlink()

print('  NotoColorEmoji')
if not (config.fonts_folder / 'NotoColorEmoji.ttf').is_file():
    print('    downloading ...')
    url = "https://noto-website-2.storage.googleapis.com/pkgs/Noto-unhinted.zip"
    urllib.request.urlretrieve(url, config.fonts_folder / 'Noto.zip')
    print('    unzipping ...')
    with zipfile.ZipFile(config.fonts_folder / 'Noto.zip', 'r') as zip_ref:
        zip_ref.extractall(config.fonts_folder)
    (config.fonts_folder / 'Noto.zip').unlink()


print('Setup Telegram Bot')
if not config.settings_file.is_file():
    print('Telegram settings')
    tel_token = input('token: ').strip()
    secret = input('new user secret: ').strip()
    settings_data = dict(
        token=tel_token,
        secret=secret,
        user=[],
        admin=[],
        blacklist=[],
        emoji={'font': "NotoColorEmoji.ttf", 'size': 109},
        #emoji={'font': "Apple Color Emoji.ttc", 'size': 160},
    )
    config.settings_file.write_text(json.dumps(settings_data, indent=4))

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


