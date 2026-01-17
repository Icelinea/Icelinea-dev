import os
import time

from loguru import logger
from ncatbot.core import BotClient, GroupMessageEvent, PrivateMessageEvent
from typeguard import typechecked

from common.io.file_sys import fs
from event.event_data import QQMessageEvent
from event.event_emitter import emitter
from services.qqbot.config import QQBotServiceConfig


class QQBotService:
    def __init__(self, config: QQBotServiceConfig):
        self._bot = BotClient()
        self._api = self._bot.run_backend(bt_uin=config.qq_num, ws_uri=config.ws_uri,
                                          ws_token=config.ws_token, debug=False, enable_webui_interaction=False)
        self._root_user = config.root
        self._groups = config.groups if config.groups is not None else []
        logger.info("QQ bot started with Napcat backend.")
        self._last_sent_time = time.time()
        self._single_img_only: bool = True

        self._init()

    def _init(self):
        @self._bot.on_group_message()
        async def echo_cmd(event: GroupMessageEvent):
            text = "".join(seg.text for seg in event.message.filter_text())
            if "echo" in text:
                if self.can_send():
                    await event.reply(text[4:])
                    self.set_timer()

        @self._bot.on_group_message()
        async def emit_plain_text_msg(event: GroupMessageEvent):
            if not (event.group_id in self._groups):
                return
            text = "".join(seg.text for seg in event.message.filter_text())
            images = event.message.filter_image()
            logger.debug(f"Received QQ message: {text}")
            if self.can_send():
                await self._emit_qq_msg(images, text, sender_id=str(event.sender.user_id), group_id=str(event.group_id))
                self.set_timer()

        @self._bot.on_private_message()
        async def on_private_message(event: PrivateMessageEvent):
            if str(event.sender.user_id) != str(self._root_user):
                return
            text = "".join(seg.text for seg in event.message.filter_text())
            images = event.message.filter_image()
            logger.debug(f"Received private QQ message: {text}")
            await self._emit_qq_msg(images, text, sender_id=str(event.sender.user_id), group_id=None)

    async def _emit_qq_msg(self, images, text, sender_id: str | None, group_id: str | None):
        if len(images) > 0:
            if self._single_img_only:
                image = images[0]
                img_path = fs.create_temp_file_descriptor(prefix='qqbot', suffix='.jpg', type='image')
                save_dir, filename = os.path.split(img_path)
                await image.download(save_dir, filename)
                if img_path.exists():
                    logger.debug(f"Received QQ image message: {img_path}")
                    emitter.emit(QQMessageEvent(message=text,
                                                images=[img_path],
                                                group_id=group_id,
                                                sender_id=sender_id))
            else:
                logger.warning("Not implemented.")
        else:
            emitter.emit(QQMessageEvent(message=text,
                                        group_id=group_id,
                                        sender_id=sender_id))

    def set_timer(self):
        self._last_sent_time = time.time()

    def can_send(self):
        now = time.time()
        print(now - self._last_sent_time)
        if now - self._last_sent_time > 5:
            return True
        logger.warning("Limit sending QQ message.")
        return False

    @typechecked
    def send_plain_message(self, group_id: str | None, receiver_id: str | None, text: str):
        assert receiver_id is not None or group_id is not None
        if group_id is not None:
            self._api.send_group_text_sync(group_id=group_id, text=text)
        else:
            self._api.send_private_plain_text_sync(user_id=receiver_id, text=text)
        logger.info(f"Sent QQ message: {text}")

    @typechecked
    def send_speech(self, group_id: str, audio_path: str):
        assert os.path.exists(audio_path)
        self._api.send_group_record_sync(group_id, audio_path)

    def start(self):
        # self._api.send_private_text_sync(self._root_user, "hello")
        # self._bot.start()
        pass

    def stop(self):
        # self._bot.bot_exit()
        pass
