from datetime import datetime
import time
import matplotlib

matplotlib.use('agg')
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartopy.feature.nightshade import Nightshade
from cartopy.feature import NaturalEarthFeature
import numpy as np
import config

plt.style.use('dark_background')


OCEAN = NaturalEarthFeature(
    'physical', 'ocean', '110m',
    edgecolor='face', facecolor=(0.5, 0.5, 1), zorder=-1)

LAND = NaturalEarthFeature(
    'physical', 'land', '110m',
    edgecolor='face', facecolor=(0.7, 1.0, 0.7), zorder=-1)

if (config.cache_folder / 'world_base.npz').is_file():
    wb = np.load(config.cache_folder / 'world_base.npz')['wb_360_52']
else:
    wb = None


def render_nightshade(w, size, now=None, alpha=0.6):
    if now is None:
        now = datetime.utcnow()
    fig = plt.figure(figsize=(1, 1), dpi=size)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Orthographic(w, 0))

    for spine in ax.spines.values():
        spine.set_color('black')
    ax.add_feature(Nightshade(now, alpha=alpha))
    ax.set_facecolor('white')
    for ax in fig.get_axes():
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(matplotlib.pyplot.NullLocator())
    plt.gca().yaxis.set_major_locator(matplotlib.pyplot.NullLocator())
    fig.canvas.draw()

    data = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    plt.clf()
    plt.close('all')
    return data.reshape(fig.canvas.get_width_height()[::-1] + (3,))

    # plt.savefig('_test.png')


def buffer_night_shade(w, size, now, alpha=0.7):
    shade = render_nightshade(w, size, now, alpha=alpha)
    shade = shade[:, :, 0] / np.max(shade[:, :, 0])
    return (wb[int(round(w))] * shade[:, :, np.newaxis]).astype(np.uint8)


def render_single_frame(w, size, now=None, light=True):
    if now is None:
        now = datetime.utcnow()
    fig = plt.figure(figsize=(1, 1), dpi=size)
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Orthographic(w, 0))
    ax.set_facecolor('black')
    ax.add_feature(LAND)
    ax.add_feature(OCEAN)
    for spine in ax.spines.values():
        spine.set_color('black')
    if light:
        ax.add_feature(Nightshade(now, alpha=0.6))

    for ax in fig.get_axes():
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(matplotlib.pyplot.NullLocator())
    plt.gca().yaxis.set_major_locator(matplotlib.pyplot.NullLocator())

    fig.canvas.draw()

    data = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    plt.clf()
    plt.close('all')
    return data.reshape(fig.canvas.get_width_height()[::-1] + (3,))


def render_earth(earth_queue, size=52, num=600):
    print('Start')
    first = True
    num_loop = 36
    earth_animation = np.zeros((num_loop, size, size, 3), dtype=np.uint8)
    while True:
        print('Loop')
        if earth_queue.empty():
            print('render')
            start = time.time()
            now = datetime.utcnow()
            if wb is not None and size == 52:
                for n, w in enumerate(np.linspace(0, 360, num_loop, endpoint=False)):
                    print(n,w)
                    earth_animation[n] = buffer_night_shade(w, size, now)
            else:
                for n, w in enumerate(np.linspace(0, 360, num_loop, endpoint=False)):
                    print(n,w)
                    earth_animation[n] = render_single_frame(w, size, now)
            earth_queue.put(earth_animation)
            print(f'{num_loop} images: {time.time() - start:.2f} s')
            if first:
                first = False
                num_loop = num
                earth_animation = np.zeros((num, size, size, 3), dtype=np.uint8)
            else:
                time.sleep(30)
        else:
            time.sleep(5)
