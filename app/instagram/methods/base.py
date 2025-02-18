from abc import ABC, abstractmethod
from pathlib import Path
from typing import cast

from ordered_set import OrderedSet
from uiautomator2 import UiObjectNotFoundError

from app.instagram.objects.audit import Audit
from app.instagram.objects.common import progress_bar
from app.instagram.objects.profile import Profile
from model.profiles import Relation
from utils import device
from utils.logger import log


class Base(ABC):
    """Abstract base class for all scrape methods."""

    @abstractmethod
    def download_media(self) -> None:
        """Downloads currenty entity's media.  
        |
            Profile: Profile picture,  
            Post: Post media,  
            Reel: Reel media,  
            Chat: None
        """
    
    @abstractmethod
    def backup(self) -> None:
        """Backs up the current entity."""


    @abstractmethod
    def audit_run(self) -> None:
        self.audit = cast(Audit, None)
        """Audits the current run."""
        
    @abstractmethod
    def start(self) -> None:
        self.save_dir = Path(".")
        """Sets the UI up before starting scrape."""
    
    def scrape(self, root: str, total: int, container: str, title: str) -> None:
        pbar = progress_bar()
        task_id = pbar.add_task(f"0/{total}", total=total, user=root)
        task = pbar.tasks[task_id]
        scanned = OrderedSet([None])
        uid = None
        last_uid = None
        pbar.start()
        while True:
            try:
                titles = list(map(lambda x: x.get_text(), device.get_elements(title)))
                # if titles and (titles[:-1] == [last_uid]):
                if titles and (titles[-1:] == scanned[-1:]) and self.__class__.__name__ == "Likes":
                    print()
                    pbar.stop()
                    break
                batch = OrderedSet(titles) - scanned
                for uid in batch:
                    scanned.add(uid)
                    pbar.update(task_id, user=uid)
                    if Profile.exists(uid):
                        profile = Profile.get(uid)
                    else:
                        uid_object = device(text=uid)
                        uid_object.click()
                        while True:
                            try:
                                profile = Profile(root)
                                break
                            except UiObjectNotFoundError:
                                if uid_object.exists() and device(container).exists():
                                    uid_object.click()
                                else:
                                    raise UiObjectNotFoundError
                        if profile.private and profile.relation ==  Relation.FOLLOW:
                            profile.generate_report(self.save_dir)
                        profile.insert()
                        device.press("back")
                        self.audit.update_count()
                    log.info(profile.log_repr)
                    pbar.update(task_id, advance=1, description=f"{task.completed+1}/{task.total}")
                if device(text="Suggested for you").exists():
                    print()
                    pbar.stop()
                    break
                last_uid = uid
                device.swipe_list(container)
            except KeyboardInterrupt:
                pbar.stop()
                log.error("Keyboard Interrupt")
                exit(0)
        review = len(list(self.save_dir.glob("*.jpg")))
        log.info(f"Scan complete. Total profiles scraped: [green]{task.completed}[/]. Profiles to review: [yellow]{review}[/]")
        