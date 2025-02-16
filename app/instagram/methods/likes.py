from typing import Literal

from app.instagram.methods.base import Base
from app.instagram.methods.common import backup
from app.instagram.resource import resourceIds
from utils import device
from utils.logger import console, log


class Likes(Base):
    def __init__(self, type: Literal["post", "reel"]) -> None:
        log.info(f"Method: [italic red]{type.capitalize()} Likes[/]\n")
        self.type = type
        match type:
            case "post":
                self.share_button = device(resourceIds.POST_SHARE_BUTTON)
            case "reel":
                self.share_button = device.get_siblings(resourceIds.REEL_LIKE_BUTTON)[4]

    def backup(self) -> None:
        """Backup current post/reel."""
        with console.status(f"Backing up current {self.type}"):
            self.share_button.click()
            backup()
            log.info(f"{self.type.capitalize()} backup complete ✅")
    
    def download_media(self) -> None:
        ...
    
    def audit(self) -> None:
        ...
        
    def start(self) -> None:
        self.backup()
        ...
