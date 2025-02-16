from app.instagram.methods.base import Base
from app.instagram.methods.common import backup
from app.instagram.objects.profile import Profile
from app.instagram.resource import resourceIds
from utils import device
from utils.logger import console, log


class Followers(Base):
    def __init__(self) -> None:
        log.info("Method: [italic red]Profile followers[/]\n")
        self.profile = Profile()
        log.info(f"{self.profile.log_repr}")

    def backup(self) -> None:
        """Backup current profile."""
        with console.status("Backing up current profile"):
            device(resourceIds.PROFILE_OPTIONS).click()
            device(text="Share this profile").click()
            backup()
            log.info("Profile backup complete ✅")

    def download_media(self) -> None:
        ...

    def audit(self) -> None:
        ...
    
    def start(self) -> None:
        self.backup()
        ...