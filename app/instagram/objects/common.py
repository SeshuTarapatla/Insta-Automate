from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from app.instagram.resource import PICTURES_FOLDER, VIDEOS_FOLDER
from utils import device


class Format:
    """Formatter class for Instagram objects."""

    @staticmethod
    def str_to_int(value: str) -> int:
        """Converts instagram human readable number to integer. Used for posts & followers notation."""
        value = value.replace(",", "").upper()
        if "K" in value:
            return int(float(value[:-1]) * 1_000)
        elif "M" in value:
            return int(float(value[:-1]) * 1_000_000)
        else:
            return int(value)

    @staticmethod
    def int_to_str(value: int) -> str:
        """Converts integer to instagram human readable number. Used for posts & followers notation."""
        if value >= 1_000_000:
            return str(value/1_000_000)[:4].rstrip(".") + "M"
        elif value >= 10_000:
            return str(value/1_000_000)[:4].rstrip(".") + "M"
        else:
            return f"{value:,}"
    
    @staticmethod
    def dt_to_str(dt: datetime) -> str:
        """Converts datetime object to instagram human readable date."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def download_last_media(dt: datetime, buffer: float = 5, wait: float = 15) -> Path:
    """Downloads the last instagram media doownloaded based on given dt. Adjust buffer for time sync issue."""
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
    device.pull(file.as_posix(), file.name)
    return Path(file.name)
