from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from time import sleep
from typing import Literal

from app.instagram.objects.common import Format
from app.instagram.resource import (
    BACKUP_ACCOUNT,
    PACKAGE,
    PICTURES_FOLDER,
    SAVE_FOLDER,
    VIDEOS_FOLDER,
    resourceIds,
)
from model.audit import Scanned
from utils import device
from utils.logger import console, log
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
    backup_account.wait_gone()

def download_media(dt: datetime, buffer: float = 5, wait: float = 15) -> Path:
    """Pulls the last instagram media downloaded based on given dt. Adjust buffer for time sync issue."""
    dt -= timedelta(seconds=buffer)
    dt_str = Format.dt_to_str(dt)
    started_at = datetime.now()
    while True:
        pictures = device.shell(f"find '{PICTURES_FOLDER.as_posix()}' -name '*.jpg' -type f -newermt '{dt_str}'").output.splitlines()
        videos = device.shell(f"find '{VIDEOS_FOLDER.as_posix()}' -name '*.mp4' -type f -newermt '{dt_str}'").output.splitlines()
        files = pictures + videos
        if files:
            break
        elif (datetime.now() - started_at).seconds > wait:
            raise TimeoutError(f"Media download timeout: {dt_str}")
    if len(files) > 1:
        raise FileExistsError(f"Multiple media exists exceeding given dt: {dt_str}")
    file = PurePosixPath(files[0])
    size = device.get_size(file)
    # Wait for media to fully download
    while True:
        sleep(0.3)
        current_size = device.get_size(file)
        if current_size == size:
            break
        size = current_size
    device.pull(file.as_posix(), file.name)
    return Path(file.name)

def mk_save_dir(type: Literal["profile", "post", "reel"], root: str, list: Scanned) -> Path:
    """Creates a save dir for scrape."""
    save_dir = SAVE_FOLDER/f"{type.capitalize()}s"/root/list.value
    save_dir.mkdir(exist_ok=True, parents=True)
    log.info(f"{type.capitalize()}: Save dir created ✅")
    return save_dir
