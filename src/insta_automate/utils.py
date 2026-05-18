import logging
from pathlib import Path
from random import shuffle as _shuffle
from shutil import move as _move

from my_modules.logger import get_logger
from send2trash import send2trash

from insta_automate.vars import IA_DIR


def set_logger_propagation(propagate: bool = True):
    for name in logging.root.manager.loggerDict:
        if name.startswith("insta_automate"):
            logging.getLogger(name).propagate = propagate


def move(src: Path, dst: Path, replace: bool = False):
    if replace and dst.exists():
        send2trash(dst)
    _move(src, dst)


def jpegs(folder: Path, shuffle: bool = False, recursive: bool = True) -> list[Path]:
    files = list(folder.rglob("*.jpg") if recursive else folder.glob("*.jpg"))
    _shuffle(files) if shuffle else None
    return files


def rm_empty_subdirs(dir: Path = IA_DIR, log: logging.Logger = get_logger(__name__)):
    empty_dirs = [
        subdir
        for subdir in dir.rglob("*/*")
        if subdir.is_dir()
        and not [hidden for hidden in subdir.parts if hidden.startswith(".")]
        and not list(subdir.glob("*"))
    ]
    if empty_dirs:
        log.warning(f"Deleting these empty subdirectories: {empty_dirs}")
        [send2trash(subdir) for subdir in empty_dirs]
