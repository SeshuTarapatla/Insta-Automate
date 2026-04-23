from logging import Logger
from pathlib import Path
import tarfile
from typing import Any, Literal, cast

from humanize import naturalsize
from my_modules.datetime_utils import Timestamp
from my_modules.logger import get_logger
from telethon.hints import ProgressCallback

from insta_automate.controllers.postgres import IaPostgres
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.utils import move
from insta_automate.vars import IA_DATABASE, IA_DIR


class IaData:
    def __init__(self, log: Logger | Any = get_logger(__name__)) -> None:
        self.log = log

    def progress_log(
        self, operation: Literal["upload", "download"], processed: int, total: int
    ):
        _prog = f"{(processed / total):.2%}"
        _done = naturalsize(processed, binary=True)
        _total = naturalsize(total, binary=True)
        self.log.info(f"{operation.capitalize()}ing backup: {_prog}. {_done}/{_total}")

    async def backup(
        self,
        progress_callback: ProgressCallback = cast(ProgressCallback, None),
    ):
        started_at = Timestamp()
        pg_bkp = IaPostgres().backup_db()
        ia_bkp = Path(f"insta-automate-backup-{Timestamp().strftime('hyphen')}.tar")

        with tarfile.open(ia_bkp, "w") as tar:
            tar.add(pg_bkp, arcname=pg_bkp.name)
            tar.add(IA_DIR, arcname=IA_DIR.name)

        tl = await IaTelegram.get_client()
        await tl.backup(
            ia_bkp,
            progress_callback=progress_callback
            or (lambda x, y: self.progress_log("upload", x, y)),
        )
        pg_bkp.unlink()
        ia_bkp.unlink()
        self.log.info(
            f"[Database + {self.total} Images] Backup complete. Total time taken: {Timestamp() - started_at}"
        )

    async def restore(
        self,
        progress_callback: ProgressCallback = cast(ProgressCallback, None),
    ):
        started_at = Timestamp()
        tl = await IaTelegram.get_client()
        ia_bkp = await tl.fetch_last_backup(
            progress_callback=progress_callback
            or (lambda x, y: self.progress_log("download", x, y))
        )
        with tarfile.open(ia_bkp, "r") as tar:
            tar.extractall()
        pg_bkp = next(Path().glob(f"{IA_DATABASE}_backup_*"))
        ia_dir = Path(IA_DIR.name)

        IaPostgres().restore_db(pg_bkp)
        pg_bkp.unlink()
        ia_bkp.unlink()
        move(ia_dir, IA_DIR, replace=True)

        self.log.info(
            f"[Database + {self.total} Images] Restore complete. Total time taken: {Timestamp() - started_at}"
        )
        return ia_dir

    @property
    def total(self) -> int:
        return len(list(IA_DIR.rglob("*.jpg")))
