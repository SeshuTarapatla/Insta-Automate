from adbutils import adb
from uiautomator2 import Device, UiObject

from utils.logger import console, log


class Android(Device):
    """Module for all android/adb related tasks."""

    def __init__(self, serial: str | None = None):
        """Create a uiautomator2 device object."""
        serial = Android.get_default_serial(serial)
        with console.status(f"Connecting to {serial}"):
            super().__init__(serial)
            log.info(f"Device connected: [bold cyan]{self.info.get("productName", serial)}[/]")
    
    def __call__(self, resourceId: str = "", text: str = "", description: str = "", className: str = "", **kwargs) -> UiObject:
        """Call for UiObjects."""
        kwargs = self.__kwargs__(resourceId, text, description, className)
        return super().__call__(**kwargs)

    def __kwargs__(self, resourceId: str = "", text: str = "", description: str = "", className: str = "", **kwargs) -> dict[str, str]:
        """Update keyword arguments."""
        if resourceId:
            kwargs["resourceId"] = resourceId
        if text:
            kwargs["text"] = text
        if description:
            kwargs["description"] = description
        if className:
            kwargs["className"] = className
        return kwargs
    
    def get_elements(self, resourceId: str) -> list[UiObject]:
        """Get list of UiObjects of given resourceId."""
        kwargs = self.__kwargs__(resourceId)
        root = self(**kwargs)
        root.wait(timeout=5)
        elements = []
        for element in root:
            elements.append(element)
        return elements

    def get_siblings(self, resourceId: str) -> list[UiObject]:
        """Get list of UiObjects silibings to a given resourceId"""
        kwargs = self.__kwargs__(resourceId)
        root = self(**kwargs)
        root.wait(timeout=5)
        siblings = []
        for element in root.sibling():
            siblings.append(element)
        return siblings
    
    def swipe_list(self, resourceId: str, filterId: str = "", duration: float = 1) -> None:
        """Scrolls over a list of elements of given resourceId.

        Args:
            resourceId (str): resourceId of list elements.
            filterId (str, optional): child resourceId to filter out invalid list elements. Defaults to "".
            duration (float, optional): drag duration in seconds. Defaults to 1.
        """
        elements = self.get_elements(resourceId)
        if filterId:
            # filter out those elements which doesn't have filterId as child element.
            elements = list(filter(lambda x: x.child(**self.__kwargs__(filterId)).exists(), elements))
        if len(elements) > 1:
            sx, ex = [self.info["displayWidth"] // 2] * 2
            sy = elements[-1].bounds()[1]
            ey = elements[0].bounds()[1]
            self.swipe(sx, sy, ex, ey, duration=duration)
        else:
            log.warning("No elements left to scroll")
    
    def print_hierarchy(self) -> None:
        """Prints output of dump_hierarchy method."""
        print(self.dump_hierarchy())

    @staticmethod
    def get_devices() -> list[str]:
        """Get serials of all connected android devices in a list."""
        return [x.serial for x in adb.iter_device()]

    @staticmethod
    def get_default_serial(serial: str | None = None) -> str:
        """Function that checks if given serial is connected. If none given, tries to return serial of currently connected device."""
        devices = Android.get_devices()
        if serial:
            if serial not in devices:
                raise NoDeviceFound(f"{serial} device is not connected.")
        else:
            if devices:
                serial = devices[0]
            else:
                raise NoDeviceFound("No adb device found to connect.")
        return serial

class NoDeviceFound(Exception):
    """Raised when android device not found"""
