import asyncio
from typing import cast

from my_modules.logger import get_logger
from telethon.types import Message

from insta_automate.controllers.device import IaDevice, IaUI
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.vars import ANDROID_SERIAL

log = get_logger(__name__)


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.device_connected: bool = False

    async def wait_for_device(self):
        notification: Message = cast(Message, None)
        while not IaDevice.connected():
            if notification is None:
                msg = "No ADB device found! Please connect and android device."
                log.error(msg)
                notification = await self.tl.bot.notify(msg)
            await asyncio.sleep(1)
        self.device_connected = True
        msg = f"ADB Device connected: {ANDROID_SERIAL}"
        log.info(msg)
        if notification is not None:
            await self.tl.bot.notify(msg, transient=True)
            await self.tl.delete_message(notification)
        self.ui = IaUI()
        self.device = self.ui.device
        self.device.app_restart()

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()

        log.info("Serve started!!")
        while True:
            await asyncio.sleep(300000)
