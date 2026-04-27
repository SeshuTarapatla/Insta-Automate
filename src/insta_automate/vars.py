from importlib.resources import files
from os import getenv
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from my_modules.win32 import get_wsl_host_ip

load_dotenv()

ASSETS = cast(Path, files("insta_automate.assets"))
BANNER: str = (ASSETS / "banner.txt").read_text(encoding="utf-8")

# Env based
ANDROID_PIN: str = getenv("ANDROID_PIN", "")
ANDROID_SERIAL: str = getenv("ANDROID_SERIAL", "")
GIT_URL: str = getenv("GIT_URL", "")
IA_ALT_ACCOUNT: str = getenv("IA_ALT_ACCOUNT", "")
IA_DIR: Path = Path(getenv("IA_DIR", ""))
IA_MAIN_ACCOUNT: str = getenv("IA_MAIN_ACCOUNT", "")
OLLAMA_URL: str | None = getenv("OLLAMA_URL")
WINDOWS_HOST: str = get_wsl_host_ip()

# Derived
ADB_SERVER_SOCKET: str = f"tcp:{WINDOWS_HOST}:5037"
ELEMENT_HEIGHT: int = 198
GENDER_INVALID_DIR: Path = IA_DIR / "gender_invalid"
GENDER_VALID_DIR: Path = IA_DIR / "gender_valid"
IA_BACKUP_CHANNEL: str = "Insta Backup"
IA_DATABASE: str = "insta_automate"
IA_DOCKER_IMAGE: str = "insta-automate"
IA_ENTITY_CHANNEL: str = "Insta Automate"
IA_FLOWS_BASE: str = "src/insta_automate/flows"
IA_NOTIFY_CHANNEL: str = "Insta Notify"
IA_PACKAGE_NAME: str = "com.instagram.android"
IA_PREFECT_WORKPOOL: str = "insta-automate-pool"
OLLAMA_VL_MODEL: str = "qwen3-vl:4b-instruct"
SCANNED_DIR: Path = IA_DIR / "scanned"
SCRAPE_QUEUE_DIR: Path = IA_DIR / "scrape_queued"
SCRAPED_DIR: Path = IA_DIR / "scraped"
FOLLOW_QUEUE_DIR: Path = IA_DIR / "follow_queued"