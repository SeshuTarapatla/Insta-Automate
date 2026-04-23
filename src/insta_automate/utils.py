import logging
from pathlib import Path
from shutil import move as _move

from send2trash import send2trash


def set_logger_propagation(propagate: bool = True):
    for name in logging.root.manager.loggerDict:
        if name.startswith("insta_automate"):
            logging.getLogger(name).propagate = propagate


def ia_int(value: str) -> int:
    value, factor = value.replace(",", "").upper(), 1
    if "M" in value:
        factor = 1_000_000
        value = value[:-1]
    elif "K" in value:
        factor = 1_000
        value = value[:-1]
    return round(float(value) * factor)


def move(src: Path, dst: Path, replace: bool = False):
    if replace and dst.exists():
        send2trash(dst)
    _move(src, dst)
