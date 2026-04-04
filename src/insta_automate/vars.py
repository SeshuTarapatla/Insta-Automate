from importlib.resources import files
from pathlib import Path
from typing import cast

from dotenv import load_dotenv

load_dotenv()

ASSETS = cast(Path, files("insta_automate.assets"))
BANNER: str = (ASSETS / "banner.txt").read_text(encoding="utf-8")

IA_IMAGE: str = "insta-automate"
IA_DATABASE: str = "insta_automate"
IA_BACKUP_CHANNEL: str = "Insta Backup"
IA_ENTITY_CHANNEL: str = "Insta Automate"
IA_NOTIFY_CHANNEL: str = "Insta Notify"
