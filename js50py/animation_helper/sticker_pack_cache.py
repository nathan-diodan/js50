import asyncio

from pyrogram import Client
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.raw.types import DocumentAttributeSticker, DocumentAttributeImageSize, DocumentAttributeFilename
from pyrogram.raw.types import InputStickerSetAnimatedEmoji
from pyrogram.raw.types import InputStickerSetShortName
from pyrogram.file_id import FileId, FileType

import config
from animation_helper.animation_functions import cache_animation


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
            sticker_attributes, image_size_attributes, file_name = self.unpack_document_attributes(document)

            emoji_code = "_".join([f'{ord(c):x}' for c in sticker_attributes.alt]).replace('_fe0f', '')
            print(f'Start {sticker_attributes.alt} ({emoji_code})')
            file_name = f'emoji_u{emoji_code}.tgs'
            sticker = config.telegram_sticker_folder / file_name

            if not sticker.with_suffix('.npz').is_file():
                fid = FileId(
                    file_type=FileType.DOCUMENT,
                    dc_id=document.dc_id,
                    media_id=document.id,
                    access_hash=document.access_hash,
                    file_reference=document.file_reference
                )
                downloader = self.client.handle_download(
                    (fid, str(config.telegram_sticker_folder.absolute()), file_name, document.size, None, None))
                loop = asyncio.get_event_loop()
                task = loop.create_task(downloader)
                loop.run_until_complete(task)
                cache_animation(sticker, sticker.with_suffix('.npz'))
            result_dict[emoji_code] = str(sticker.absolute())
        return result_dict



