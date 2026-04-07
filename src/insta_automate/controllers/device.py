__all__ = ["adb"]

from pathlib import Path
from sys import platform
from typing import Literal

from adbutils import AdbClient, adb
from my_modules.scrcpy import Scrcpy
from uiautomator2 import Device
from uiautomator2._selector import UiObject

from insta_automate.vars import (
    ANDROID_PIN,
    ANDROID_SERIAL,
    IA_PACKAGE_NAME,
    WINDOWS_HOST,
)

adb = adb if platform == "win32" else AdbClient(WINDOWS_HOST, 5037)


class IaDevice(Device):
    def __init__(
        self,
        serial: str = ANDROID_SERIAL,
        pin: str = ANDROID_PIN,
        package: str = IA_PACKAGE_NAME,
    ):
        super().__init__(adb.device(serial))
        self.pin = pin
        self.ui = IaUI(self)
        self.package = package
        self.start_scrcpy()

    def __call__(
        self, resourceId: str | None = None, text: str | None = None, **kwargs
    ) -> UiObject:
        kwargs["resourceId"] = resourceId
        kwargs["text"] = text
        kwargs = {key: value for key, value in kwargs.items() if value}
        return super().__call__(**kwargs)

    def start_scrcpy(self):
        if self.locked:
            self.unlock()
        self.scrcpy = Scrcpy(self.serial)
        self.scrcpy.start()

    def unlock(self):
        self.ui.charging_animation.wait_gone()
        self.screen_on()
        self.swipe(0, 2000, 0, 0, steps=5)
        for digit in self.pin:
            self.ui.pin_digit(digit).click()
        self.ui.pin_enter.click()

    def app_start(self, package_name: str = IA_PACKAGE_NAME, *args, **kwargs):
        package_name = package_name or self.package
        return super().app_start(self.package, wait=True)

    def app_restart(self, package_name: str = IA_PACKAGE_NAME):
        self.app_stop(package_name)
        return self.app_start(package_name)

    def dump_hierarchy(  # type: ignore[override]
        self,
        dump_file="dump.xml",
        compressed=False,
        pretty=False,
        max_depth: int | None = None,
    ) -> bool:
        dump = super().dump_hierarchy(compressed, pretty, max_depth)
        Path(dump_file).write_text(dump, encoding="utf-8")
        return True

    @property
    def locked(self) -> bool:
        return self.ui.lock_screen.exists()

    @staticmethod
    def connected() -> bool:
        return any(device.serial == ANDROID_SERIAL for device in adb.device_list())


class IaUI:
    def __init__(self, device: IaDevice | None = None) -> None:
        self.device = device if device else IaDevice()

        self.lock_screen = self.resourceId("keyguard_root_view", "system")
        self.pin_enter = self.resourceId("key_enter", "system")
        self.charging_animation = self.resourceId("charge_screen_view", "vivo")

    def pin_digit(self, digit: int | str) -> UiObject:
        return self.device(self._resourceId("vivo_digit_text", "system"), str(digit))

    def _resourceId(
        self,
        key: str,
        app: Literal["system", "vivo", "instagram"] = "instagram",
    ) -> str:
        root = {
            "system": "com.android.systemui",
            "vivo": "com.vivo.systemuiplugin",
            "instagram": IA_PACKAGE_NAME,
        }[app]
        return f"{root}:id/{key}"

    def resourceId(
        self,
        key: str,
        app: Literal["system", "vivo", "instagram"] = "instagram",
    ) -> UiObject:
        return self.device(self._resourceId(key, app))
