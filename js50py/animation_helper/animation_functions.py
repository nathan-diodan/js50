import os
import shutil
import subprocess
from datetime import datetime

import emoji
import freetype
import numpy as np
import pytz
import qrcode
import skvideo.io
from PIL import Image, ImageOps

import config

tz = pytz.timezone(config.time_zone)
tgs_tool = str((config.base_dir / 'tools' / 'tgs' / 'cli.js').absolute())


def make_square(im, size=64, fill_color=(0, 0, 0, 0)):
    x, y = im.size
    new_im = Image.new('RGB', (size, size), fill_color)
    new_im.paste(im, (int((size - x) / 2), int((size - y) / 2)))
    return new_im


def cache_animation(sticker, cache_file):
    print('preparing animation')
    temp_folder = cache_file.parent / f'temp_{cache_file.name}'
    temp_folder.mkdir(exist_ok=True, parents=True)
    subprocess.run(['node', tgs_tool, '--width', '64', '--height', '64', '--out_path',
                    f'{temp_folder.absolute()}/frame_%04d.png', str(sticker.absolute())],
                   check=True, stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
    frame_list = []
    for frame, image_path in enumerate(sorted(temp_folder.glob('*.png'))):
        pil_image = Image.open(image_path).convert('RGB')
        frame_list.append((np.array(pil_image.convert('RGB'), dtype=np.uint8)))

    all_frames = np.zeros((len(frame_list), 64, 64, 3), dtype=np.uint8)
    for n, frame in enumerate(frame_list):
        all_frames[n] = frame

    np.savez_compressed(cache_file, frames=all_frames)
    shutil.rmtree(temp_folder)
    sticker.unlink()


def load_video(video_cache_file):
    metadata = skvideo.io.ffprobe(video_cache_file)['video']
    fps = int(round(float(metadata["@nb_frames"])/float(metadata['@duration'])))
    the_video = skvideo.io.vread(str(video_cache_file))
    return {'animation': True, 'frames': the_video, 'fps': fps}


def load_photo(photo_cache_file, size=64, box=True, fill_color=(0,0,0,0)):
    pil_image = Image.open(photo_cache_file)
    if box:
        pil_image.thumbnail((size, size)) #, Image.ANTIALIAS)
        pil_image = make_square(pil_image, size=size, fill_color=fill_color)
    else:
        pil_image = ImageOps.fit(pil_image, (size, size), Image.ANTIALIAS)
    return np.array(pil_image.convert('RGB'), dtype=np.uint8)[None, ...]


def prepare_video(video_cache_file_raw, video_cache_file):
    subprocess.run(['ffmpeg', '-i', str(video_cache_file_raw.absolute()), '-vf', 'scale=64:64:force_original_aspect_ratio=decrease,pad=64:64:-1:-1:color=black',
                    '-c:v', 'libx264',  '-crf', '0', '-an', '-y',
                    str(video_cache_file.absolute())],
                   check=True, stdout=open(os.devnull, 'wb'), stderr=open(os.devnull, 'wb'))
    video_cache_file_raw.unlink()


def load_animation(animation_file):
    cache_file = animation_file.with_suffix('.npz')
    if cache_file.is_file():
        frames = np.load(cache_file)['frames']
    else:
        cache_animation(animation_file, cache_file)
        frames = np.load(cache_file)['frames']
    return {'animation': True, 'frames': frames, 'fps': 60}


def prepare_animation(animation_file):
    cache_file = animation_file.with_suffix('.npz')
    if not cache_file.is_file():
         cache_animation(animation_file, cache_file)


def convert_bgra_to_rgb(buf):
    blue = buf[:,:,0]
    green = buf[:,:,1]
    red = buf[:,:,2]
    return np.dstack((red, green, blue))


def load_qr(data, rgb=(255, 255, 255), size=64):
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=False)
    np_qr = np.invert(np.array(qr.modules, dtype=np.bool))
    qr_size = np_qr.shape[0]
    full = np.ones((size, size, 3), dtype=np.uint8) * 255
    for x in [3, 4]:
        for y in [3, 4]:
            for n, c in enumerate(rgb):
                full[x:qr_size * 2 + x:2, y:qr_size * 2 + y:2, n] = np_qr * c
    return {'mover': True, 'frame': full, 'fps': 5}


def get_time_quad(earth=None, earth_frame=0, rgb=(1, 1, 1), display_shape=(64, 64)):
    now = datetime.now(tz)
    day = text2numpy(f'{now.day:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    month = text2numpy(f'{now.month:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    hour = text2numpy(f'{now.hour:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    minute = text2numpy(f'{now.minute:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    # second = text2numpy(f'{now.second:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    # millisecond = text2numpy(f'{int(now.microsecond/3E4)*3:02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
    height, width = hour.shape[:2]
    buffer_frame = np.zeros((display_shape[0], display_shape[1], 3), dtype=np.uint8)
    if earth is not None:
        x_start = (display_shape[0] - earth.shape[1])//2
        y_start = (display_shape[1] - earth.shape[2])//2
        bs = np.index_exp[x_start:x_start+earth.shape[1], y_start:y_start+earth.shape[2]]
        buffer_frame[bs] = earth[earth_frame]

    display_data = [[day, month], [hour, minute]]
    for x in [0, 1]:
        for y in [0, 1]:
            x_start = x * (display_shape[0] - height)
            y_start = y * (display_shape[1] - width + 3)
            bs = np.index_exp[x_start:x_start+height, y_start:y_start+width-3]
            buffer_frame[bs][display_data[x][y][:, :-3] != 0] = display_data[x][y][:, :-3][display_data[x][y][:, :-3] != 0]

    return buffer_frame


def get_time(display_seconds=True, rgb=(1, 1, 1), display_shape=(64, 64)):
    now = datetime.now(tz)
    main_text = f'{now.hour:02d}:{now.minute:02d}'
    clock_main = text2numpy(main_text, mono=True, include_emoji=False, face_size=18, rgb=rgb)
    buffer_frame = np.zeros((display_shape[0], display_shape[1], 3), dtype=np.uint8)
    if display_seconds:
        clock_sub = text2numpy(f'{now.second:02d}.{int(now.microsecond/1E4):02d}', mono=True, include_emoji=False, face_size=18, rgb=rgb)
        distance_top = (display_shape[0] - clock_main.shape[0] - clock_sub.shape[0]) // 3
        distance_left_main = (display_shape[1] - clock_main.shape[1]) // 2
        distance_left_sub = (display_shape[1] - clock_sub.shape[1]) // 2
        buffer_frame[distance_top:distance_top + clock_main.shape[0], distance_left_main:distance_left_main + clock_main.shape[1]] = clock_main
        start_sub = 2 * distance_top + clock_main.shape[0]
        buffer_frame[start_sub:start_sub+clock_sub.shape[0], distance_left_sub:distance_left_sub + clock_sub.shape[1]] = clock_sub
    else:
        distance_top = (display_shape[0] - clock_main.shape[0]) // 2
        distance_left = (display_shape[1] - clock_main.shape[1]) // 2
        buffer_frame[distance_top:distance_top + clock_main.shape[0], distance_left:distance_left + clock_main.shape[1]] = clock_main
    return buffer_frame


def text2numpy(text, mono=False, include_emoji=True, face_size=20, rgb=(1, 1, 1)):
    if include_emoji:
        face_size = 109
    if include_emoji:
        emoji_face = freetype.Face("fonts/NotoColorEmoji.ttf")
        emoji_face.set_char_size(face_size * 64)

    if mono:
        base_face = freetype.Face('fonts/CourierPrime-Regular.ttf')
    else:
        base_face = freetype.Face('fonts/OpenSans-SemiBold.ttf')

    base_face.set_char_size(face_size * 64)
    is_emoji = np.zeros(len(text), dtype=np.bool)
    for i, c in enumerate(text):
        is_emoji[i] = c in emoji.UNICODE_EMOJI
    # First pass to compute bbox
    width, height, baseline = 0, 0, 0
    previous = 0
    for i, c in enumerate(text):
        if is_emoji[i] and include_emoji:
            face = emoji_face
        elif is_emoji[i]:
            continue
        else:
            face = base_face
        face.load_char(c)
        slot = face.glyph
        bitmap = slot.bitmap
        height = max(height,
                     bitmap.rows + max(0, -(slot.bitmap_top - bitmap.rows)))
        baseline = max(baseline, max(0, -(slot.bitmap_top - bitmap.rows)))
        kerning = face.get_kerning(previous, c)
        # print(f'{slot.advance.x} {slot.advance.x >> 6} | {kerning.x} {kerning.x >> 6}')
        # width += (slot.advance.x >> 6) + (kerning.x >> 6)
        width += (slot.advance.x >> 6) + (kerning.x >> 6)
        previous = c

    Z = np.zeros((height, width, 4), dtype=np.uint8)

    # print(f'original size (h,w) {height}, {width}')
    # Second pass for actual rendering
    x, y = 0, 0
    previous = 0
    for i, c in enumerate(text):
        if is_emoji[i] and include_emoji:
            face = emoji_face
            face.load_char(c, freetype.FT_LOAD_COLOR)
        elif is_emoji[i]:
            continue
        else:
            face = base_face
            face.load_char(c)
        slot = face.glyph
        bitmap = slot.bitmap
        top = slot.bitmap_top
        w, h = bitmap.width, bitmap.rows
        y = max(0, height - baseline - top)
        kerning = face.get_kerning(previous, c)
        x += (kerning.x >> 6)
        if c in emoji.UNICODE_EMOJI:
            Z[y:y + h, x:x + w] += np.array(bitmap.buffer, dtype=np.uint8).reshape(h, w, 4)
        else:
            binary_mask = np.array(bitmap.buffer, dtype='ubyte').reshape(h, w)
            Z[y:y + h, x:x + w, 0] = binary_mask * rgb[2]
            Z[y:y + h, x:x + w, 1] = binary_mask * rgb[1]
            Z[y:y + h, x:x + w, 2] = binary_mask * rgb[0]
            Z[y:y + h, x:x + w, 3] = binary_mask
        x += (slot.advance.x >> 6)
        previous = c
    return convert_bgra_to_rgb(Z)


def load_text(text, rgb=(1, 1, 1), scale=5, display_shape=(64, 64), skip=10):
    Z = text2numpy(text, rgb=rgb)
    final_height = int(round(Z.shape[0] / scale))
    final_width = int(round(Z.shape[1] * (final_height / Z.shape[0])))
    pil_image = Image.fromarray(Z)
    pil_image = pil_image.resize((final_width, final_height))
    frame = np.array(pil_image.convert('RGB'), dtype=np.uint8)
    print(f'shape frame {frame.shape}')
    distance_top = (display_shape[0] - final_height) // 2
    if final_width > display_shape[1]:
        buffer_frame = np.zeros((display_shape[0], final_width+skip+display_shape[1], 3), dtype=np.uint8)
        buffer_frame[distance_top:distance_top+final_height, final_width+skip:] = frame[:, :display_shape[1]]
        buffer_frame[distance_top:distance_top+final_height, :final_width] = frame
    else:
        distance_left = (display_shape[1] - final_width) // 2
        buffer_frame = np.zeros((display_shape[0], display_shape[1], 3), dtype=np.uint8)
        buffer_frame[distance_top:distance_top+final_height, distance_left:distance_left+final_width] = frame

    print(f'buffer shape frame {buffer_frame.shape}')
    return {'mover': True, 'frame': buffer_frame, 'fps': 45}

