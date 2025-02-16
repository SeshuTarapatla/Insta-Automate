from shutil import move
from typing import Literal

from send2trash import send2trash

from app.instagram.methods.base import Base
from app.instagram.methods.common import backup, mk_save_dir
from app.instagram.objects.audit import Audit
from app.instagram.objects.post import Post
from app.instagram.resource import resourceIds
from app.vars import args
from model.audit import Scanned
from utils import device
from utils.logger import console, log


class Likes(Base):
    def __init__(self, type: Literal["reel", "post"]) -> None:
        log.info(f"Method: [italic red]{type.capitalize()} Likes[/]\n")
        self.type: Literal["reel", "post"] = type
        match type:
            case "post":
                self.share_button = device(resourceIds.POST_SHARE_BUTTON)
                self.menu = resourceIds.POST_MENU_BUTTON
                self.like_count = device(resourceIds.POST_LIKE_COUNT)
                self.drag_text = "Likes"
            case "reel":
                reel_like_button_siblings = device.get_siblings(resourceIds.REEL_LIKE_BUTTON)
                self.share_button = reel_like_button_siblings[4]
                self.menu = resourceIds.REEL_MENU_BUTTON
                self.like_count = reel_like_button_siblings[1]
                self.drag_text = "Views & likes"

    def backup(self) -> None:
        """Backup current post/reel."""
        if args.resume or not args.backup:
            return
        with console.status(f"Backing up current {self.type}"):
            self.share_button.click()
            backup()
            log.info(f"{self.type.capitalize()}: Backup completed ✅")
    
    def download_media(self) -> None:
        """Download current post/reel."""
        with console.status(f"Downloading current {self.type}"):
            report = device(resourceIds.APP_FULLSCREEN).screenshot()
            media = Post.download(self.menu)
            self.post = Post(self.type, media)
            self.save_dir = mk_save_dir(self.type, self.post.id, Scanned.LIKES)
            self.media = self.save_dir.parent/(self.post.hash+".jpg")
            if not self.media.exists():
                move(media, self.save_dir.parent)
                report.save(self.media)
            else:
                send2trash(media)
        log.info(f"{self.type.capitalize()}: Media downloaded ✅\n")
    
    def audit_run(self) -> None:
        self.audit = Audit(self.post.id, Scanned.LIKES)
        self.audit.insert()
        
    def start(self) -> None:
        self.backup()
        self.download_media()
        self.audit_run()
        log.info(self.post.log_repr)
        log.info(f"Scanning [yellow]LIKES[/] list of [italic]{self.post.id}[/]\n")
        self.like_count.click()
        device(resourceIds.LIKES_DRAG_PILL).drag_to(0, 0)
        self.scrape(self.post.id, Post.get_mean(), resourceIds.LIKE_USER_CONTAINER, resourceIds.LIKE_USERNAME)
