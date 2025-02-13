from shutil import which
from subprocess import DEVNULL, Popen
from time import sleep
from typing import cast

from rich.status import Status

from utils.android import Android
from utils.logger import log


class Scrcpy:
    """Scrcpy module to start/stop android mirroring sessions."""

    def __init__(self, serial: str | None = None) -> None:
        """Creates an scrcpy object with a given `serial`. If no serial is provided, finds it from connected devices."""
        # init self variables
        self.serial : str = ""
        self.process: Popen[bytes] = cast(Popen[bytes], None)
        self.delay  : float = 3
        # pre-checks for scrcpy and device
        Scrcpy.check_installation()
        self.serial = Android.get_default_serial(serial)
    
    def start(self) -> None:
        """Start android mirroring."""
        with Status(f"Starting scrcpy session for {self.serial}"):
            self.process = Popen(f"scrcpy -s {self.serial} -S", stdout=DEVNULL, stderr=DEVNULL)
            sleep(self.delay)
        log.info("Scrcpy session started")
    
    def stop(self) -> None:
        """Stop android mirroring"""
        if self.process:
            self.__del__()
            log.info("Scrcpy session ended")
    
    def __del__(self) -> None:
        """Garbage collect the object."""
        self.process.kill()
    
    @staticmethod
    def check_installation() -> None:
        """Verify scrcpy exists.
        
        Raises:
            FileNotFoundError: If scrcpy is not found in path.
        """
        binary = which("scrcpy")
        if binary is None:
            raise FileNotFoundError('Scrcpy not found. Please install and add "scrcpy" to path.')
        