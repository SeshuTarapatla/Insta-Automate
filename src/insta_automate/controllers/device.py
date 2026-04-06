__all__ = ["adb"]

from os import getenv

from adbutils import AdbClient

from insta_automate.vars import ADB_DEVICE_SERIAL

adb = AdbClient(getenv("WINDOWS_HOST"))


class IaDevice:
    @staticmethod
    def connected() -> bool:
        return any(device.serial == ADB_DEVICE_SERIAL for device in adb.device_list())
