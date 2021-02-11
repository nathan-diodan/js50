from pyowm import OWM
import cairosvg
import config
import numpy as np
import json

owm = OWM(config.settings['owm_token'])
mgr = owm.weather_manager()
weather_conditions = json.loads((config.base_dir / 'js50py' / 'animation_helper' / 'weather_icon.json').read_text())
icon_folder = config.cache_folder / 'weather-icons' / 'svg'


def svg2array(svg_path, size):
    tree = cairosvg.parser.Tree(bytestring=svg_path.read_bytes())
    surf = cairosvg.surface.PNGSurface(tree, None, 300, output_width=size, output_height=size).cairo
    im = np.frombuffer(surf.get_data(), np.uint8)
    return im.reshape(size, size, 4)[:, :, 3]


def get_weather_data(size):
    observation = mgr.weather_at_place(config.settings['location'])
    w = observation.weather
    condition = weather_conditions[str(w.weather_code)]
    svg_path = icon_folder / f"wi-{condition['icon']}.svg"
    temp = f"{round(w.temp['temp']-273.15,1):.1f}C"
    return svg2array(svg_path, size), temp
