import asyncio

from my_modules.datetime_utils import Timestamp
from my_modules.logger import get_logger

log = get_logger(__name__)


class Internet:
    def __init__(
        self, host: str = "1.1.1.1", port: int = 80, timeout: float = 3.0
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    async def is_active(self) -> bool:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def verify_network(self):
        if not await self.is_active:
            log.error("Internet disconnected. Pausing till network is back.")
            started_at = Timestamp()
            while not await self.is_active:
                await asyncio.sleep(1)
            log.info(f"Internet is back. Disconnected for {Timestamp() - started_at}.")
