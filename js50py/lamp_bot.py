import logging
from functools import wraps
from io import BytesIO
import subprocess
import json

import emoji
import zmq
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram import ParseMode
from telegram.ext import MessageFilter
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler
from telegram.ext import Updater, Filters

import config
from animation_helper.animation_functions import prepare_animation, prepare_video, load_photo

zmq_context = zmq.Context()


class FilterEmoji(MessageFilter):
    def filter(self, message):
        return message.text in emoji.UNICODE_EMOJI


#  Socket to talk to server
print("Connecting to tcp://127.0.0.1:2222")
socket = zmq_context.socket(zmq.REQ)
socket.connect("tcp://127.0.0.1:2222")
print('Connected')
settings_data = json.loads(config.settings.read_text())


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in settings_data['user'] + settings_data['admin']:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)

    return wrapped


def restricted_admin(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in settings_data['admin']:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)

    return wrapped


updater = Updater(token=settings_data['token'], use_context=True)

dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def download_to_buffer(file_id, context):
    raw_data = BytesIO()
    send_file = context.bot.get_file(file_id)
    send_file.download(out=raw_data)
    raw_data.seek(0)
    return raw_data


def send_animation_data(socket, np_array, fps=30, flags=0, copy=True, track=False):
    meta_data = dict(
        type='animation_data',
        dtype=str(np_array.dtype),
        shape=np_array.shape,
        fps=fps,
    )
    print(f'Sending animation data ({np_array.shape[0]} frames)')
    socket.send_json(meta_data, flags | zmq.SNDMORE)
    socket.send(np_array, flags, copy=copy, track=track)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_music(socket, name, flags=0):
    meta_data = dict(
        type='music',
        name=name
    )
    print(f'Sending music viz {name}')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_text(socket, text, flags=0):
    meta_data = dict(
        type='text',
        text=text
    )
    print(f'Sending text {text}')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_qr(socket, data, flags=0):
    meta_data = dict(
        type='qr',
        data=data
    )
    print(f'Sending QR code "{data}"')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_apple(socket, command, flags=0):
    meta_data = dict(
        type='apple',
        command=command
    )
    print(f'Apple Home Kit {command}"')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print(f"Received: {message}")


def send_opengl(socket, flags=0):
    meta_data = dict(
        type='opengl',
    )
    print(f'Sending openGL')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_clock(socket, clock_type, flags=0):
    mode = clock_type.partition('set_clock_')[2]
    meta_data = dict(
        type='clock',
        mode=mode
    )
    print(f'Sending clock')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def send_cache_file(socket, file_path, file_type='video', flags=0):
    meta_data = dict(
        type='cache',
        file_type=file_type,
        cache=str(file_path.absolute()),
    )
    print(f'Sending {file_type} {file_path.absolute()}')
    socket.send_json(meta_data, flags)
    message = socket.recv_string()
    print("Received reply %s" % message)


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")
    print(update.effective_user.id)
    print(context)


def secret(update, context):
    if update.effective_user.id in settings_data['blacklist']:
        return None
    if not settings_data['user']:
        if update.effective_user.id not in settings_data['admin']:
            settings_data['admin'].append(update.effective_user.id)
    else:
        if update.effective_user.id not in settings_data['user']:
            settings_data['user'].append(update.effective_user.id)
    config.settings.write_text(json.dumps(settings_data))
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"User {update.effective_user.id} added")


@restricted
def qr(update, context):
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"Preparing QR code ...")
    data = update['message']['text'].partition('/qr')[2].strip()
    send_qr(socket, data=data)
    reply_massage.edit_text(text=f"The QR code is now on display.")


@restricted
def apple_lamp(update, context):
    keyboard = [[InlineKeyboardButton("Setup", callback_data='set_apple_setup'),
                 InlineKeyboardButton("Start", callback_data='set_apple_start')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)


@restricted_admin
def admin(update, context):

    keyboard = [[InlineKeyboardButton("Power off", callback_data='set_admin_off'),
                 InlineKeyboardButton("Restart", callback_data='set_admin_reboot')],
                [InlineKeyboardButton("Change secret", callback_data='set_admin_set_secret'),
                 InlineKeyboardButton("Status", callback_data='set_admin_status')],
                [InlineKeyboardButton("List users", callback_data='set_admin_list_user'),
                 InlineKeyboardButton("Remove user", callback_data='set_admin_delete_user')],
                [InlineKeyboardButton("Add admin", callback_data='set_admin_add'),
                 InlineKeyboardButton("Remove admin", callback_data='set_admin_remove')]
                ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)


@restricted_admin
def admin_callbacks(update, context, query):
    mode = query.data.partition('set_admin_')[2]
    print(mode)
    if mode == 'reboot':
        query.edit_message_text(text=f"Rebooting! See you in a second")
        subprocess.Popen(["sudo", "reboot"], stdin=None, stdout=None, stderr=None)

    elif mode == 'off':
        query.edit_message_text(text=f"Shutting down! 👋")
        subprocess.Popen(["sudo", "poweroff"], stdin=None, stdout=None, stderr=None)
    elif mode == 'status':
        cpu_temp_raw = subprocess.run(["/opt/vc/bin/vcgencmd", "measure_temp"], capture_output=True)
        cpu_temp = cpu_temp_raw.stdout.decode().partition('temp=')[2].partition("'")[0]
        disk_usage_raw = subprocess.run(["df", "/", "-h"], capture_output=True)
        disk_usage = disk_usage_raw.stdout.decode().split('\n')[1].partition('%')[0].rpartition(" ")[2]
        uptime_raw = subprocess.run(["uptime"], capture_output=True)
        uptime = uptime_raw.stdout.decode().partition('up ')[2].partition(",")[0].strip()
        query.edit_message_text(text=f"🌡 {cpu_temp} C\n\n💾 {disk_usage}%\n\n⏱ {uptime}")


@restricted
def clock(update, context):
    keyboard = [[InlineKeyboardButton("World", callback_data='set_clock_world'),
                 InlineKeyboardButton("Weather", callback_data='set_clock_weather')],
                [InlineKeyboardButton("Timer", callback_data='set_clock_timer'),
                 InlineKeyboardButton("Stopwatch", callback_data='set_clock_stop')]
                ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)


@restricted
def animation(update, context):
    keyboard = [[InlineKeyboardButton("Rainfall", callback_data='set_mode_hap'),
                 InlineKeyboardButton("Firework", callback_data='set_mode_telegram')],
                [InlineKeyboardButton("Soundtrace", callback_data='set_mode_music'),]]

    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text('Please choose:', reply_markup=reply_markup)


@restricted
def callback(update, context):
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    need_answer = True
    query.answer()
    if query.data == 'set_mode_music':
        send_music(socket, name='spectral')
    elif query.data == 'set_mode_music2':
        send_opengl(socket)
    elif query.data.startswith('set_clock'):
        send_clock(socket, query.data)
    elif query.data.startswith('set_admin'):
        admin_callbacks(update, context, query)
        need_answer = False
    elif query.data == 'set_apple_setup':
        send_apple(socket, command='setup')
    elif query.data == 'set_apple_start':
        send_apple(socket, command='start')

    if need_answer:
        query.edit_message_text(text="Selected option: {}".format(query.data))


@restricted
def video(update, context):
    video_cache_file_raw = config.telegram_video_folder / f'new_raw.mp4'
    video_cache_file = config.telegram_video_folder / f'new.mp4'
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"A video! Start Downloading ({update.message.effective_attachment.file_size/1024:.1f} kB)...")
    raw_video_file = context.bot.get_file(update.message.effective_attachment.file_id)
    raw_video_file.download(video_cache_file_raw)
    prepare_video(video_cache_file_raw, video_cache_file)
    send_cache_file(socket, video_cache_file, file_type='video')
    reply_massage.edit_text(text=f"The video️ is now on display.")


@restricted
def sticker(update, context):

    sticker_cache_file = config.telegram_sticker_folder / f'{update.message.sticker.file_unique_id}.npz'

    if update.message.sticker.is_animated:
        reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                                 text=f"An animated {update.message.sticker.emoji} sticker!")
        if not sticker_cache_file.is_file():
            reply_massage.edit_text(text=f"This animated {update.message.sticker.emoji} sticker from *{update.message.sticker.set_name.replace('_', ' ').upper()}* is a new one. Let me work on it!", parse_mode=ParseMode.MARKDOWN)
            raw_sticker_file = context.bot.get_file(update.message.sticker.file_id)
            raw_sticker_file.download(sticker_cache_file.with_suffix('.tgs'))
            prepare_animation(sticker_cache_file.with_suffix('.tgs'))
        send_cache_file(socket, sticker_cache_file, file_type='sticker')

    else:
        reply_massage = context.bot.send_message(chat_id=update.effective_chat.id, text=f"A {update.message.sticker.emoji} sticker!")
        raw_sticker_data = download_to_buffer(update.message.sticker.file_id, context)
        send_animation_data(socket, load_photo(raw_sticker_data, box=True))

    reply_massage.edit_text(text=f"*{update.message.sticker.set_name.replace('_', ' ').upper()}* {update.message.sticker.emoji} sticker️ is now on display.", parse_mode=ParseMode.MARKDOWN)


@restricted
def photo(update, context):
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"A photo! Start Downloading ({update.message.photo[0].file_size/1024:.1f} kB)...")

    raw_photo_data = download_to_buffer(update.message.photo[0].file_id, context)
    photo_data = load_photo(raw_photo_data, box=False)
    send_animation_data(socket, photo_data, fps=5)
    reply_massage.edit_text(text=f"The photo is now on display.")


@restricted
def text(update, context):
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"A text! Rendering ...")
    send_text(socket, update.message.text)
    reply_massage.edit_text(text=f"The text is now on display.")


@restricted
def cb_emoji(update, context):
    emoji_value = update.message.text
    emoji_code = "_".join([f'{ord(c):x}' for c in emoji_value]).replace('_fe0f', '')
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"An emoji! (U+{emoji_code})")
    animated_emoji_file = config.telegram_sticker_folder / f'emoji_u{emoji_code}.npz'
    emoji_file = config.emoji_folder / f'emoji_u{emoji_code}.png'
    if animated_emoji_file.is_file():
        send_cache_file(socket, animated_emoji_file, file_type='sticker')
        reply_massage.edit_text(text=f"{emoji_value} (U+{emoji_code}) is now animated on display.")
    elif emoji_file.is_file():
        photo_data = load_photo(emoji_file, box=True)
        send_animation_data(socket, photo_data, fps=5)
        reply_massage.edit_text(text=f"{emoji_value} (U+{emoji_code}) is now on display.")
    else:
        send_text(socket, emoji_value)
        reply_massage.edit_text(text=f"{emoji_value} (U+{emoji_code}) is now rendered and on display.")


@restricted
def catch_all(update, context):
    reply_massage = context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=f"What is this?")
    pass


emoji_filter = FilterEmoji()
handler_list = [
    CommandHandler('start', start),
    CommandHandler(settings_data['secret'], secret),
    CommandHandler('animation', animation),
    CommandHandler('clock', clock),
    CommandHandler('apple', apple_lamp),
    CommandHandler('admin', admin),
    CommandHandler('qr', qr),
    MessageHandler(Filters.sticker, sticker),
    MessageHandler(Filters.document.gif | Filters.video, video),
    MessageHandler(Filters.photo, photo),
    MessageHandler(emoji_filter, cb_emoji),
    MessageHandler(Filters.text & (~Filters.command), text),
    MessageHandler(Filters.all, catch_all)
]
for handler in handler_list:
    dispatcher.add_handler(handler)

updater.dispatcher.add_handler(CallbackQueryHandler(callback))
print('Setup complete')
updater.start_polling()
