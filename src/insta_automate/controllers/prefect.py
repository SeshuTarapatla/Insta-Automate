import asyncio

from my_modules.logger import get_logger

from insta_automate.controllers.device import IaDevice, IaUI
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.vars import ANDROID_SERIAL

log = get_logger(__name__)


class Prefect:
    def __init__(self) -> None:
        self.tl = IaTelegram()
        self.device_connected: bool = False

    async def wait_for_device(self):
        notified: bool = False
        while not IaDevice.connected():
            if not notified:
                msg = "No ADB device found! Please connect and android device."
                log.error(msg)
                await self.tl.bot.notify(msg)
                notified = True
            await asyncio.sleep(1)
        self.device_connected = True
        msg = f"ADB Device connected: {ANDROID_SERIAL}"
        log.info(msg)
        if notified:
            await self.tl.bot.notify(msg)
        self.ui = IaUI()
        self.device = self.ui.device
        self.device.app_restart()

    async def serve(self):
        await self.tl.start()
        await self.wait_for_device()

        log.info("Serve started!!")
        while True:
            await asyncio.sleep(300000)
