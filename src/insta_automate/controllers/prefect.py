import asyncio
from typing import cast

from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from telethon.events import NewMessage
from telethon.types import Message

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.models.telegram import IaMessages

log = get_logger(__name__)


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.device_connected: bool = False

    async def wait_for_device(self):
        notification: Message = cast(Message, None)
        while not IaDevice.connected():
            if notification is None:
                log.error(IaMessages.DEVICE_DISCONNECTED)
                notification = await self.tl.bot.notify(IaMessages.DEVICE_DISCONNECTED)
            await asyncio.sleep(1)
        self.device_connected = True
        log.info(IaMessages.DEVICE_CONNECTED)
        if notification is not None:
            await self.tl.bot.notify(IaMessages.DEVICE_CONNECTED, transient=True)
            await self.tl.purge_adb_notifications()
        self.device = IaDevice()
        self.device.app_restart()

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()

        @self.tl.on(NewMessage(chats=self.tl.entity_channel))
        async def new_entity_message(event: NewMessage.Event):
            log.info(f"New Entity received: [green]{event.message.text}[/]")

        log.info("Server started!!")
        await handle_await(self.tl.run_until_disconnected())
