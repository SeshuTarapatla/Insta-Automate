from shutil import which
from subprocess import DEVNULL, Popen
from time import sleep
from typing import cast

from rich.status import Status

from utils.android import Android, NoDeviceFound
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
        all_devices = Android.get_devices()
        if serial:
            if serial in all_devices:
                self.serial = serial
            else:
                raise NoDeviceFound(f"{serial} device is not connected.")
        elif Android.get_devices():
            self.serial = Android.get_devices()[0]
        else:
            raise NoDeviceFound("No android device found to connect.")
    
    def start(self) -> None:
        """Start android mirroring."""
        with Status(f"Starting scrcpy session for {self.serial}"):
            self.process = Popen(f"scrcpy -s {self.serial} -S", stdout=DEVNULL, stderr=DEVNULL)
            sleep(self.delay)
        log.info("Scrcpy session started")
    
    def stop(self) -> None:
        """Stop android mirroring"""
        if self.process:
            log.info("Scrcpy session ended")
            self.process.kill()
    
    def __del__(self) -> None:
        """Garbage collect the object."""
        self.stop()
    
    @staticmethod
    def check_installation() -> None:
        """Verify scrcpy exists.
        
        Raises:
            FileNotFoundError: If scrcpy is not found in path.
        """
        binary = which("scrcpy")
        if binary is None:
            raise FileNotFoundError('Scrcpy not found. Please install and add "scrcpy" to path.')
        