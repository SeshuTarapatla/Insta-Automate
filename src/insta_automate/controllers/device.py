__all__ = ["adb"]

from pathlib import Path
from sys import platform
from typing import Literal

from adbutils import AdbClient, adb
from my_modules.datetime_utils import Timestamp
from my_modules.logger import get_logger
from my_modules.scrcpy import Scrcpy
from uiautomator2 import Device
from uiautomator2._selector import UiObject

from insta_automate.exceptions import EntityAccessResolutionError
from insta_automate.models.entity import Entity, EntityAccess, EntityType
from insta_automate.vars import (
    ANDROID_PIN,
    ANDROID_SERIAL,
    IA_ALT_ACCOUNT,
    IA_MAIN_ACCOUNT,
    IA_PACKAGE_NAME,
    WINDOWS_HOST,
)

adb = adb if platform == "win32" else AdbClient(WINDOWS_HOST, 5037)
log = get_logger(__name__)


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
        self.unlock()
        self.start_scrcpy()

    def __call__(
        self, resourceId: str | None = None, text: str | None = None, **kwargs
    ) -> UiObject:
        kwargs["resourceId"] = resourceId
        kwargs["text"] = text
        kwargs = {key: value for key, value in kwargs.items() if value}
        return super().__call__(**kwargs)

    def start_scrcpy(self):
        if platform != "win32":
            return
        self.scrcpy = Scrcpy(self.serial)
        self.scrcpy.start()

    def unlock(self):
        if not self.locked:
            return
        log.info("Device is locked. Unlocking the device...")
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

    def switch_account(self, account: Literal["main", "alt"]) -> bool:
        match account:
            case "main":
                switch = self.ui.main_account.click
            case "alt":
                switch = self.ui.alt_account.click
            case _:
                raise ValueError(
                    f'{account} is not a valid account identifier. Use: ["main", "alt"].'
                )
        while self.ui.back_button.exists:
            self.ui.back_button.click()
            self.sleep(0.5)
        if not self.ui.profile_tab.exists():
            self.app_restart()
            self.ui.profile_tab.wait()
        self.ui.profile_tab.long_click()
        switch()
        self.press("back")
        return True

    def entity_access(self, entity: Entity, timeout: float = 30) -> EntityAccess:
        self.switch_account("alt")
        self.open_url(entity.url)
        match entity.type:
            case EntityType.PROFILE:
                access = self._profile_entity_access(timeout)
            case EntityType.POST:
                access = self._post_entity_access(timeout)
            case EntityType.REEL:
                access = self._reel_entity_access(entity.url, timeout)
        if access:
            return access
        else:
            raise EntityAccessResolutionError(
                f"Failed to resolve access type of {entity.id}."
            )

    def _profile_entity_access(self, timeout: float = 30) -> EntityAccess | None:
        started_at = Timestamp()
        while (Timestamp() - started_at).seconds <= timeout:
            if self.ui.private_account_banner.exists:
                return EntityAccess.PRIVATE
            elif self.ui.profile_tabs_container.exists:
                return EntityAccess.PUBLIC

    def _post_entity_access(self, timeout: float = 30) -> EntityAccess | None:
        started_at = Timestamp()
        while (Timestamp() - started_at).seconds <= timeout:
            if self.ui.private_account_banner.exists:
                return EntityAccess.PRIVATE
            elif self.ui.post_save_button.exists:
                return EntityAccess.PUBLIC

    def _reel_entity_access(self, url: str, timeout: float = 30):
        def _reel_author() -> str:
            self(resourceId="com.instagram.android:id/clips_author_username").must_wait(
                timeout=timeout / 2
            )
            return self(
                resourceId="com.instagram.android:id/clips_author_username"
            ).get_text()

        author1 = _reel_author()
        self.open_url(url)
        author2 = _reel_author()
        if author1 == author2:
            return EntityAccess.PUBLIC
        else:
            return EntityAccess.PRIVATE

    @property
    def locked(self) -> bool:
        return self.ui.lock_screen.exists()

    @staticmethod
    def connected() -> bool:
        return any(device.serial == ANDROID_SERIAL for device in adb.device_list())


class IaUI:
    def __init__(self, device: IaDevice | None = None) -> None:
        self.device = device if device else IaDevice()

        # system
        self.charging_animation = self.resourceId("charge_screen_view", "vivo")
        self.lock_screen = self.resourceId("keyguard_root_view", "system")
        self.pin_enter = self.resourceId("key_enter", "system")

        # app
        self.alt_account = self.text(IA_ALT_ACCOUNT)
        self.back_button = self.content("Back")
        self.main_account = self.text(IA_MAIN_ACCOUNT)
        self.post_save_button = self.resourceId("row_feed_button_save")
        self.private_account_banner = self.text("This account is private")
        self.profile_tab = self.resourceId("profile_tab")
        self.profile_tabs_container = self.resourceId("profile_tabs_container")
        self.reels_author = self.resourceId("clips_author_username")

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

    def text(self, text: str) -> UiObject:
        return self.device(text=text)

    def content(self, description: str) -> UiObject:
        return self.device(description=description)
