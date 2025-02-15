from app.instagram.methods.base import Base
from app.instagram.objects.profile import Profile
from app.instagram.resource import BACKUP_ACCOUNT, resourceIds
from utils import device
from utils.logger import log


class Followers(Base):
    def __init__(self) -> None:
        log.info("Method: [italic red]Profile followers[/]\n")
        self.profile = Profile()
        log.info(f"Profile: {self.profile.log_repr}")

    def download_media(self) -> None:
        ...

    def audit(self) -> None:
        ...
    
    def backup(self) -> None:
        """Backup root profile."""
        device(resourceIds.PROFILE_OPTIONS).click()
        device(text="Share this profile").click()
        device(text="Search").click()
        device.send_keys(BACKUP_ACCOUNT)
        backup_account = device(resourceIds.SHARE_USERNAME, text=BACKUP_ACCOUNT)
        if not backup_account.wait(timeout=5):
            raise RuntimeError("Backup account not found.")
        backup_account.click()
        device(text="Send").click()


    
    def start(self) -> None:
        self.backup()
        self.download_media()
        ...