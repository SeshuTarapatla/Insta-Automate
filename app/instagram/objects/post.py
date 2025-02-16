from datetime import datetime
from pathlib import Path
from typing import Literal

from xxhash import xxh64

from app.instagram.methods.common import download_media
from app.instagram.resource import resourceIds
from model.audit import Audit
from model.base import session
from uiautomator2 import UiObject

from utils import device
from utils.misc import time_limit


class Post:
    def __init__(self, type: Literal["reel", "post"], media: Path) -> None:
        self.type = type
        self.media = media
        self.hash = xxh64(self.media.read_bytes()).hexdigest()
    
    def generate(self) -> None:
        ...
    
    @property
    def id(self) -> str:
        if prev := session.query(Audit).where(Audit.root.like(f"%{self.hash}%")).limit(1).one_or_none():
            return prev.root
        count = session.query(Audit.root).where(Audit.root.like(f"{self.type}%")).distinct().count()
        index = count+1
        return f"{self.type}-{str(index).rjust(4,"0")}-{self.hash}"
    
    @staticmethod
    def download(menu: str) -> Path:
        started_at = datetime.now()
        device(menu).click()
        device(text="Download").click()
        return download_media(started_at)
    