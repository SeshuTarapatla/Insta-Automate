from typing import cast

from app.vars import SERIAL, args
from utils.android import Android
from utils.scrcpy import Scrcpy

__all__ = ["device", "scrcpy"]


# init common utils
if args.setup:
    device = cast(Android, None)
    scrcpy = cast(Scrcpy, None)
else:
    device = Android(SERIAL)
    scrcpy = Scrcpy(SERIAL)