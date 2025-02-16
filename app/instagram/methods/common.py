from datetime import datetime

from app.instagram.resource import BACKUP_ACCOUNT, PACKAGE, resourceIds
from utils import device
from utils.logger import console
from utils.misc import time_limit


def resume() -> None:
    """Resumes previous scrape entity from Backup account."""
    with console.status("Resuming previous scrape entity"):
        home_tab = device(resourceIds.HOME_TAB)
        home_tab.click() if home_tab.exists() else restart()
        device(resourceIds.INBOX_TAB).click()
        device.wait(resourceIds.INBOX_USER_CONTAINER)
        backup_account = device(text=BACKUP_ACCOUNT)
        started_at = datetime.now()
        while not backup_account.exists():
            device.swipe_list(resourceIds.INBOX_USER_CONTAINER, resourceIds.INBOX_USERNAME)
            time_limit(started_at)
        backup_account.click()
        last_message = device.get_elements(resourceIds.MESSAGE_CONTAINER)[-1]
        last_message.click()
        

def restart() -> None:
    """Restarts Instagram app."""
    device.app_stop(PACKAGE)
    device.app_start(PACKAGE)
    device.wait(resourceIds.HOME_TAB)

def backup() -> None:
    """Backs up current scrape entity to Backup account. Entrypoint should be share menu."""
    device(text="Search").click()
    device.send_keys(BACKUP_ACCOUNT)
    backup_account = device(resourceIds.SHARE_USERNAME, text=BACKUP_ACCOUNT)
    if not backup_account.wait(timeout=5):
        raise RuntimeError("Backup account not found.")
    backup_account.click()
    device(text="Send").click()
