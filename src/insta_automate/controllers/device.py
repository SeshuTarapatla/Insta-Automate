__all__ = ["adb"]

from functools import wraps
from io import BytesIO
from pathlib import Path
from sys import platform
from time import sleep
from typing import Callable, Literal, ParamSpec, TypeVar

from adbutils import AdbClient, adb
from my_modules.datetime_utils import Timestamp
from my_modules.inet import Internet
from my_modules.logger import get_logger
from PIL.Image import Image
from retry import retry
from uiautomator2 import Device
from uiautomator2._selector import UiObject
from wsl_bridge.scrcpy import ScrcpyClient

from insta_automate.exceptions import EntityAccessResolutionError
from insta_automate.models.entity import Entity, EntityAccess
from insta_automate.models.meta import EntityType
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

P = ParamSpec("P")
R = TypeVar("R")


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
        self.current_user: Literal["main", "alt"] = "alt"
        self.inet = Internet()

    def _wait_for_network(self):
        return self.inet.wait_for_network()

    def lock(self):
        self.screen_off()
        self.sleep(1)

    @retry(tries=3, delay=5)
    def __call__(
        self, resourceId: str | None = None, text: str | None = None, **kwargs
    ) -> UiObject:
        if resourceId and not resourceId.startswith("com"):
            resourceId = self.ui._resourceId(resourceId)
        kwargs["resourceId"] = resourceId
        kwargs["text"] = text
        kwargs = {key: value for key, value in kwargs.items() if value}
        return super().__call__(**kwargs)

    @staticmethod
    def ui_retry(method: Callable[P, R]) -> Callable[P, R]:
        @wraps(method)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            self: IaDevice = args[0]  # type: ignore[assignment]
            try:
                return method(*args, **kwargs)
            except Exception:
                log.error(f"UI Exception occurred for: {method}")
                self.app_restart()
                return method(*args, **kwargs)

        return wrapper

    def start_scrcpy(self):
        try:
            log.info(f"Starting scrcpy session for Device({self.serial})")
            ScrcpyClient.start(self.serial)
        except Exception:
            log.error("Failed to start scrcpy session. [bold red]Service 404[/].")

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
        self.unlock()
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
        package: str | None = IA_PACKAGE_NAME,
    ) -> bool:
        dump = super().dump_hierarchy(compressed, pretty, max_depth)
        if package:
            dump = "\n".join(line for line in dump.splitlines() if package in line)
        Path(dump_file).write_text(dump, encoding="utf-8")
        return True

    def open_url(self, url: str, wait: float = 1):
        self._wait_for_network()
        super().open_url(url)
        sleep(wait)

    def open_entity(self, entity: Entity):
        by_url = False
        if entity.type == EntityType.PROFILE:
            self._ia_home()
            if not self.ui.search_tab.exists:
                self.app_restart()
                self.ui.search_tab.must_wait()
            self.ui.search_tab.click()
            self.ui.search_bar.click()
            self.send_keys(entity.id, clear=True)
            self.sleep(1)
            if (result := self.ui.search_result.child(text=entity.id)).exists:
                result.click()
            else:
                by_url = True
        if entity.type != EntityType.PROFILE or by_url:
            self.open_url(entity.url)

    def swipe_list(self, elements: list[UiObject], duration: float = 1):
        if len(elements) > 1:
            return self.swipe(
                *elements[-1].center(), *elements[0].center(), duration=duration
            )

    @ui_retry
    def switch_account(self, account: Literal["main", "alt"]) -> bool:
        self._wait_for_network()
        match account:
            case "main":
                self.current_user = "main"
                switch = self.ui.main_account.click
            case "alt":
                self.current_user = "alt"
                switch = self.ui.alt_account.click
            case _:
                raise ValueError(
                    f'{account} is not a valid account identifier. Use: ["main", "alt"].'
                )
        self._ia_home()
        if not self.ui.profile_tab.exists():
            self.app_restart()
            self.ui.profile_tab.wait()
        self.ui.profile_tab.long_click()
        switch()
        self.press("back")
        self.sleep(1)
        return True

    def _ia_home(self):
        if self.ui.likes_drag_bar.exists or self.ui.share_drag_bar.exists:
            self.press("back")
        while self.ui.back_button.exists:
            self.ui.back_button.click()
            self.sleep(0.5)

    def determine_entity_access(
        self, entity: Entity, timeout: float = 30
    ) -> EntityAccess:
        self._wait_for_network()
        self.switch_account("alt")
        self.open_entity(entity)
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
        self._wait_for_network()
        while (Timestamp() - started_at).seconds <= timeout:
            if (
                self.ui.private_account_banner.exists
                or self.ui.private_profile_banner.exists
            ):
                return EntityAccess.PRIVATE
            elif self.ui.profile_tabs_container.exists:
                return EntityAccess.PUBLIC

    def _post_entity_access(self, timeout: float = 30) -> EntityAccess | None:
        started_at = Timestamp()
        self._wait_for_network()
        while (Timestamp() - started_at).seconds <= timeout:
            if (
                self.ui.private_account_banner.exists
                or self.ui.private_profile_banner.exists
            ):
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

        self._wait_for_network()
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
        self.action_bar_title = self.resourceId("action_bar_title")
        self.alt_account = self.text(IA_ALT_ACCOUNT)
        self.back_button = self.content("Back")
        self.follower_container = self.resourceId("follow_list_container")
        self.follower_container_id = self.resourceId("follow_list_username")
        self.follower_container_loader = self.resourceId("row_load_more_button")
        self.like_container = self.resourceId("row_user_container_base")
        self.like_container_id = self.resourceId("row_user_primary_name")
        self.likes_drag_bar = self.resourceId("bottom_sheet_drag_handle_prism")
        self.main_account = self.text(IA_MAIN_ACCOUNT)
        self.post_comment_button = self.resourceId("row_feed_button_comment")
        self.post_group_buttons = self.resourceId("row_feed_view_group_buttons")
        self.post_like_button = self.resourceId("row_feed_button_like")
        self.post_save_button = self.resourceId("row_feed_button_save")
        self.private_account_banner = self.text("This account is private")
        self.private_profile_banner = self.text("This profile is private")
        self.profile_bio = self.resourceId("profile_user_info_compose_view").child(
            className="android.widget.TextView"
        )
        self.profile_followers = self.resourceId(
            "profile_header_familiar_followers_value"
        )
        self.profile_following = self.resourceId(
            "profile_header_familiar_following_value"
        )
        self.profile_header = self.resourceId("profile_header_container")
        self.profile_id = self.action_bar_title
        self.profile_name = self.resourceId("profile_header_full_name_above_vanity")
        self.profile_posts = self.resourceId("profile_header_familiar_post_count_value")
        self.profile_tab = self.resourceId("profile_tab")
        self.profile_tabs_container = self.resourceId("profile_tabs_container")
        self.reel_like_count = self.resourceId("like_count")
        self.reels_author = self.resourceId("clips_author_username")
        self.search_bar = self.resourceId("action_bar_search_edit_text")
        self.search_result = self.resourceId("row_search_user_info_container")
        self.search_tab = self.resourceId("search_tab")
        self.share_drag_bar = self.resourceId(
            "direct_private_share_action_bar_container_view"
        )
        self.suggested_for_you = self.text("Suggested for you")

    def pin_digit(self, digit: int | str) -> UiObject:
        return self.device(self._resourceId("vivo_digit_text", "system"), str(digit))

    @staticmethod
    def _resourceId(
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

    @staticmethod
    def height(ui_object: UiObject) -> int:
        _, y1, _, y2 = ui_object.bounds()
        return y2 - y1

    @staticmethod
    def image(
        screenshot: Image,
        format: Literal["png", "jpg"] = "png",
        name: str = "screenshot",
    ) -> BytesIO:
        buffer = BytesIO()
        buffer.name = f"{name}.{format}"
        screenshot.save(buffer, format=format)
        buffer.seek(0)
        return buffer

    @property
    def post_like_count(self) -> UiObject:
        x1, _ = self.post_like_button.center()
        x2, _ = self.post_comment_button.center()
        for element in self.post_group_buttons.child(className="android.widget.Button"):
            if x1 < element.center()[0] < x2:
                return element
        # if (element := self.device(textContains="Liked by")).exists:
        #     return element
        raise Exception
