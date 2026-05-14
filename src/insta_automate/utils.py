import logging
from pathlib import Path
from random import shuffle as _shuffle
from shutil import move as _move

from send2trash import send2trash


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
