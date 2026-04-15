from dataclasses import dataclass

from insta_automate.vars import ANDROID_SERIAL


@dataclass(frozen=True)
class IaMessages:
    DEVICE_DISCONNECTED: str = "No ADB device found! Please connect an android device."
    DEVICE_CONNECTED: str = f"ADB Device connected: {ANDROID_SERIAL}"
