from importlib.resources import files
from os import getenv
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from my_modules.win32 import get_wsl_host_ip

load_dotenv()

ASSETS = cast(Path, files("insta_automate.assets"))
BANNER: str = (ASSETS / "banner.txt").read_text(encoding="utf-8")

IA_ALT_ACCOUNT: str = getenv("IA_ALT_ACCOUNT", "")
IA_BACKUP_CHANNEL: str = "Insta Backup"
IA_DATABASE: str = "insta_automate"
IA_DOCKER_IMAGE: str = "insta-automate"
IA_ENTITY_CHANNEL: str = "Insta Automate"
IA_FLOWS_BASE: str = "src/insta_automate/flows"
IA_MAIN_ACCOUNT: str = getenv("IA_MAIN_ACCOUNT", "")
IA_NOTIFY_CHANNEL: str = "Insta Notify"
IA_PACKAGE_NAME: str = "com.instagram.android"
IA_PREFECT_WORKPOOL: str = "insta-automate-pool"

WINDOWS_HOST: str = get_wsl_host_ip()
ADB_SERVER_SOCKET: str = f"tcp:{WINDOWS_HOST}:5037"
ANDROID_PIN: str = getenv("ANDROID_PIN", "")
ANDROID_SERIAL: str = getenv("ANDROID_SERIAL", "")
GIT_URL: str = getenv("GIT_URL", "")
IA_DIR: Path = Path("~/Pictures/insta-automate").expanduser()
ELEMENT_HEIGHT: int = 198
