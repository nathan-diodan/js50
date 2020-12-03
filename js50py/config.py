from pathlib import Path
import logging
import json

app_name = 'JS50'
version_number = (0, 1, 0)
version = f'{version_number[0]}.{version_number[1]}.{version_number[2]}'
app_author = 'Hagen Eckert'
url = 'https://github.com/nathan-diodan/js50'

base_dir = Path(__file__).absolute().parent.parent
fonts_folder = base_dir / 'fonts'
cache_folder = base_dir / 'cache'
telegram_sticker_folder = cache_folder / 'animated_sticker'
telegram_video_folder = cache_folder / 'video'
tgs_tool_folder = base_dir / 'tools' / 'tgs'
settings_file = base_dir / 'config.json'

log_level = logging.WARNING

time_zone = 'Europe/Berlin'

if settings_file.is_file():
    settings = json.loads(settings_file.read_text())
else:
    settings = {}
