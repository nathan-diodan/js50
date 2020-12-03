import asyncio
from pathlib import Path

from pyrogram import Client
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.raw.types import DocumentAttributeSticker, DocumentAttributeImageSize, DocumentAttributeFilename
from pyrogram.raw.types import InputStickerSetAnimatedEmoji
from pyrogram.raw.types import InputStickerSetShortName
from pyrogram.utils import encode_file_ref

from js50py import config
from js50py.animation_helper.animation_functions import cache_animation

class FileData:
    def __init__(
        self, *, media_type: int = None, dc_id: int = None, document_id: int = None, access_hash: int = None,
        thumb_size: str = None, peer_id: int = None, peer_type: str = None, peer_access_hash: int = None,
        volume_id: int = None, local_id: int = None, is_big: bool = None, file_size: int = None, mime_type: str = None,
        file_name: str = None, date: int = None, file_ref: str = None
    ):
        self.media_type = media_type
        self.dc_id = dc_id
        self.document_id = document_id
        self.access_hash = access_hash
        self.thumb_size = thumb_size
        self.peer_id = peer_id
        self.peer_type = peer_type
        self.peer_access_hash = peer_access_hash
        self.volume_id = volume_id
        self.local_id = local_id
        self.is_big = is_big
        self.file_size = file_size
        self.mime_type = mime_type
        self.file_name = file_name
        self.date = date
        self.file_ref = file_ref


class StickerCollector:

    def __init__(self, config_file=None):
        if config_file is None:
            self.client = Client("LEDmatrix")
        else:
            self.client = Client("LEDmatrix", config_file=config_file)
        self.client.start()

    @staticmethod
    def unpack_document_attributes(document):
        sticker_attributes, image_size_attributes, file_name = None, None, None
        for attribute in document.attributes:
            if isinstance(attribute, DocumentAttributeSticker):
                sticker_attributes = attribute
            elif isinstance(attribute, DocumentAttributeImageSize):
                image_size_attributes = attribute
            elif isinstance(attribute, DocumentAttributeFilename):
                file_name = attribute.file_name

        return sticker_attributes, image_size_attributes, file_name

    def get_set_emojis_dict(self, set_name: str) -> dict:
        if set_name:
            input_sticker_set_short_name = InputStickerSetShortName(short_name=set_name)
        else:
            input_sticker_set_short_name = InputStickerSetAnimatedEmoji()
        sticker_set = self.client.send(GetStickerSet(stickerset=input_sticker_set_short_name))

        result_dict = dict()

        for document in sticker_set.documents:
            # sticker_set.documents: list of stickers in the pack
            sticker_attributes, image_size_attributes, file_name = self.unpack_document_attributes(document)

            emoji_code = "_".join([f'{ord(c):x}' for c in sticker_attributes.alt]).replace('_fe0f', '')
            print(f'Start {sticker_attributes.alt} ({emoji_code})')
            data = FileData(
                media_type=15,
                dc_id=document.dc_id,
                document_id=document.id,
                access_hash=document.access_hash,
                thumb_size="",
                peer_id=0,
                peer_type='',
                peer_access_hash=0,
                volume_id=0,
                local_id=0,
                file_size=document.size,
                is_big=False,
                file_ref=encode_file_ref(document.file_reference))

            file_name = f'emoji_u{emoji_code}.tgs'
            sticker = config.telegram_sticker_folder / file_name
            if not sticker.with_suffix('.npz').is_file():
                downloader = self.client.handle_download((data, str(config.telegram_sticker_folder.absolute()), file_name, None, None))
                loop = asyncio.get_event_loop()
                task = loop.create_task(downloader)
                loop.run_until_complete(task)
                cache_animation(sticker, sticker.with_suffix('.npz'))
            result_dict[emoji_code] = str(sticker.absolute())
        return result_dict



