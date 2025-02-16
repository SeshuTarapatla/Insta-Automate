from app.instagram.methods.base import Base
from app.instagram.methods.common import backup, mk_save_dir
from app.instagram.objects.audit import Audit
from app.instagram.objects.profile import Profile
from app.instagram.resource import resourceIds
from app.vars import args
from model.audit import Scanned
from utils import device
from utils.logger import console, log


class Followers(Base):
    def __init__(self) -> None:
        log.info("Method: [italic red]Profile followers[/]\n")
        with console.status("Reading current profile"):
            self.profile = Profile()
            self.list = self.choose_list()
            self.save_dir = mk_save_dir('profile', self.profile.id, self.list)

    def backup(self) -> None:
        """Backup current profile."""
        with console.status("Backing up current profile"):
            device(resourceIds.PROFILE_OPTIONS).click()
            device(text="Share this profile").click()
            backup()
            log.info("Profile: Backup completed ✅")

    def download_media(self) -> None:
        """Download current profile dp."""
        self.media = self.save_dir.parent/(self.profile.id+".jpg")
        if not self.media.exists():
            with console.status("Downloading profile media"):
                self.profile.generate_report(self.save_dir.parent)
        log.info("Profile: Media downloaded ✅")

    def audit(self) -> None:
        ...
    
    def start(self) -> None:
        self.backup()
        self.download_media()
        ...
    
    def choose_list(self) -> Scanned:
        if prev := Audit.get_previous(self.profile.id):
            list = prev.list
        elif self.profile.followers < self.profile.following:
            list = Scanned.FOLLOWERS
        else:
            list = Scanned.FOLLOWING
        match args.flist:
            case 1:
                list = Scanned.FOLLOWERS
            case 2:
                list = Scanned.FOLLOWING
        return list

