from datetime import datetime
from itertools import chain
from math import ceil
from pathlib import Path
from statistics import mean
from typing import Literal

from sqlalchemy import func, or_
from xxhash import xxh64

from app.instagram.methods.common import download_media
from app.instagram.objects.profile import Profile
from app.instagram.resource import SAVE_FOLDER
from model.audit import Audit
from model.base import session
from utils import device


class Post:
    def __init__(self, type: Literal["reel", "post"], media: Path) -> None:
        self.type = type
        self.media = media
        self.hash = xxh64(self.media.read_bytes()).hexdigest()
    
    @property
    def id(self) -> str:
        hashes = list(SAVE_FOLDER.glob("*/*/*.jpg"))
        match = list(filter(lambda x: self.hash in x.as_posix(), hashes))
        if match:
            return match[0].parent.stem
        count = session.query(Audit.root).where(Audit.root.like(f"{self.type}%")).distinct().count()
        index = count + 1
        return f"{self.type}-{str(index).rjust(4, "0")}"
    
    @staticmethod
    def download(menu: str) -> Path:
        started_at = datetime.now()
        device(menu).click()
        device(text="Download").click()
        download = device(text="Download This Media File")
        if download.exists(1):
            download.click()
        return download_media(started_at)
    
    @property
    def log_repr(self) -> str:
        return (
            f"[magenta bold]{self.type.capitalize()}[/]("
            f"ID: [cyan bold]{self.id}[/], "
            f"Hash: [dark_orange3 bold italic]{self.hash}[/])"
        )

    @staticmethod
    def get_mean() -> int:
        counts = session.query(func.count()).where(or_(Profile.root.like('post%'), Profile.root.like('reel%'))).group_by(Profile.root).all()
        counts = counts if counts else [(100,)]
        return max(ceil(mean(chain(*counts))), 100)
    