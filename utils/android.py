from pathlib import PurePosixPath
from typing import Literal
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
            log.info(f"Device connected: [cyan]{self.info.get("productName", serial)}[/]")
    
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
    
    def swipe_list(self, resourceId: str, min_y: int = 100, duration: float = 1, direction: Literal["up", "down"] = "up") -> None:
        """Scrolls over a list of elements of given resourceId.

        Args:
            resourceId (str): resourceId of list elements.
            min_y (int, optional): minimum visible pixels on y axis for last element. Defaults to 100.
            duration (float, optional): drag duration in seconds. Defaults to 1.
            direction (Literal[&quot;up&quot;, &quot;down&quot;], optional): Scroll direction. Defaults to "up".

        Raises:
            RuntimeError: If no scroll elements present.
        """
        elements = self.get_elements(resourceId)
        if len(elements) > 1:
            sx, sy, ex, ey = elements[-1].bounds()
            last = -1 if (ey - sy) >= min_y else -2
            sx, ex = [self.info["displayWidth"] // 2] * 2
            sy = elements[last].bounds()[1]
            ey = elements[0].bounds()[1]
            if direction == "down":
                sy,ey = ey,sy
            self.swipe(sx, sy, ex, ey, duration=duration)
        else:
            log.error("No elements left to scroll")
            raise RuntimeError
    
    def get_text(self, resourceId: str, default: str = "") -> str:
        """Function that return text of an element if exists, else returns default value."""
        kwargs = self.__kwargs__(resourceId)
        element = self(**kwargs)
        if element.exists:
            return element.get_text()
        return default
    
    def print_hierarchy(self) -> None:
        """Prints output of dump_hierarchy method."""
        print(self.dump_hierarchy())
    
    def wait(self, resourceId: str, timeout: int = 10) -> None:
        """Wait for an element to appear on screen. If not found in given time, raises an exception."""
        kwargs = self.__kwargs__(resourceId)
        status = self(**kwargs).wait(timeout=timeout)
        if not status:
            raise Exception(f"Element with resourceId: {resourceId} not found. [Time limit exceeded]")
    
    def get_size(self, file: PurePosixPath | str) -> int:
        """Get size of a given file in bytes."""
        file = file.as_posix() if isinstance(file, PurePosixPath) else file
        return int(self.shell(f"stat -c %s {file}").output.splitlines()[0])

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
