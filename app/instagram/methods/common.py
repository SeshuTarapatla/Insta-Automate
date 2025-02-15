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
        device(resourceIds.INBOX_USER_CONTAINER).wait()
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
    device(resourceIds.HOME_TAB).wait(timeout=10)
