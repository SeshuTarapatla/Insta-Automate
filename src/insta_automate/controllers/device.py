__all__ = ["adb"]

from sys import platform

from adbutils import AdbClient, adb

from insta_automate.vars import ANDROID_SERIAL, WINDOWS_HOST

adb = adb if platform == "win32" else AdbClient(WINDOWS_HOST, 5037)


class IaDevice:
    @staticmethod
    def connected() -> bool:
        return any(device.serial == ANDROID_SERIAL for device in adb.device_list())
