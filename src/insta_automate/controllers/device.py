__all__ = ["adb"]

from adbutils import adb

from insta_automate.vars import ANDROID_SERIAL


class IaDevice:
    @staticmethod
    def connected() -> bool:
        return any(device.serial == ANDROID_SERIAL for device in adb.device_list())
