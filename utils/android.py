from adbutils import adb
from uiautomator2 import Device


class Android(Device):
    """Module for all android/adb related tasks."""

    def __init__(self, serial: str | None = None):
        devices = Android.get_devices()
        if serial:
            if serial not in devices:
                raise NoDeviceFound(f"{serial} device is not connected.")
        else:
            if devices:
                serial = devices[0]
            else:
                raise NoDeviceFound("No adb device found to connect.")
        super().__init__(serial)

    @staticmethod
    def get_devices() -> list[str]:
        """Get serials of all connected android devices in a list."""
        return [x.serial for x in adb.iter_device()]


class NoDeviceFound(Exception):
    """Raised when android device not found"""
