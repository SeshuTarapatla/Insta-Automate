from adbutils import adb


class Android:
    """Module for all android/adb related tasks."""

    @staticmethod
    def get_devices() -> list[str]:
        """Get serials of all connected android devices in a list."""
        return [x.serial for x in adb.iter_device()]


class NoDeviceFound(Exception):
    """Raised when android device not found"""
