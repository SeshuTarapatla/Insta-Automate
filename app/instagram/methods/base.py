from abc import ABC, abstractmethod
from pathlib import Path
from typing import cast

from ordered_set import OrderedSet

from app.instagram.objects.audit import Audit
from app.instagram.objects.common import progress_bar
from app.instagram.objects.profile import Profile
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
        scanned = OrderedSet([])
        last_uid = None
        pbar.start()
        while True:
            try:
                uid = None
                batch = list(OrderedSet(map(lambda x: x.get_text(), device.get_elements(title))))
                if batch[-1] == last_uid:
                    print()
                    pbar.stop()
                    break
                batch = list(OrderedSet(batch) - scanned)
                for uid in batch:
                    scanned.add(uid)
                    pbar.update(task_id, user=uid)
                    if Profile.exists(uid):
                        profile = Profile.get(uid)
                    else:
                        device(text=uid).click()
                        profile = Profile(root)
                        if profile.private:
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
                last_uid = batch[-1]
                device.swipe_list(container, title)
            except KeyboardInterrupt:
                pbar.stop()
                log.error("Keyboard Interrupt")
                exit(0)
            except Exception as exception:
                pbar.stop()
                raise RuntimeError(f"UI Error: {exception}")
        review = len(list(self.save_dir.glob("*.jpg")))
        log.info(f"Scan complete. Total profiles scraped: [green]{task.completed}[/]. Profiles to review: [yellow]{review}[/]")
        