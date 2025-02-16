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
            self.profile = Profile.get_or_create()
            self.list = self.choose_list()
            self.save_dir = mk_save_dir('profile', self.profile.id, self.list)
            self.profile.insert()

    def backup(self) -> None:
        """Backup current profile."""
        if args.resume or not args.backup:
            return
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
        log.info("Profile: Media downloaded ✅\n")

    def audit_run(self) -> None:
        self.audit = Audit(self.profile.id, self.list)
        self.audit.insert()
    
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

    def start(self) -> None:
        self.backup()
        self.download_media()
        self.audit_run()
        total = self.profile.followers if self.audit.list == Scanned.FOLLOWERS else self.profile.following
        log.info(self.profile.log_repr)
        log.info(f"Scanning [yellow]{self.list.value.upper()}[/] list of [italic]@{self.profile.id}[/]\n")
        device(text=self.list.value).click()
        self.scrape(self.profile.id, total, resourceIds.FOLLOWER_CONTAINER, resourceIds.FOLLOWER_TITLE)
