from enum import StrEnum, auto
from pathlib import Path

from dotenv import get_key, set_key
from my_modules.logger import get_logger

from insta_automate.utils import jpegs
from insta_automate.vars import (
    ENTITY_DIR,
    FOLLOW_QUEUE_DIR,
    IA_DIR,
    SCRAPE_QUEUE_DIR,
    TRIGGERS,
)


log = get_logger(__name__)


class Queue(list[Path]):
    class Order(StrEnum):
        NAME = auto()
        DATE = auto()
        COUNT = auto()

    def __init__(
        self,
        directory: Path,
        env_key: str | None = None,
        order: Order = Order.NAME,
        inverse: bool = False,
    ) -> None:
        self.key = env_key
        self.directory = directory
        self.mode = order
        self.inverse = inverse

        self.load_queue()

    def load_queue(self):
        self.entries = (
            [
                entry.strip()
                for entry in (get_key(TRIGGERS, self.key) or "").split(",")
                if entry
            ]
            if self.key
            else []
        )
        self.pref_queue = [self.directory / entry for entry in self.entries]
        rem_queue = [
            folder
            for folder in self.directory.glob("*")
            if folder.is_dir() and folder.name not in self.entries
        ]
        match self.mode:
            case Queue.Order.NAME:

                def name_key(folder: Path):
                    return folder

                key = name_key
            case Queue.Order.DATE:

                def date_key(folder: Path):
                    return folder.lstat().st_birthtime

                key = date_key
            case Queue.Order.COUNT:

                def count_key(folder: Path):
                    return len(jpegs(folder))

                key = count_key
        self.rem_queue = sorted(rem_queue, key=key, reverse=self.inverse)
        super().__init__(self.pref_queue + self.rem_queue)

    def __str__(self) -> str:
        return str([x.name for x in self])

    def __repr__(self) -> str:
        return repr(self.entries)

    def update(self):
        if self.key:
            set_key(TRIGGERS, self.key, ",".join(self.entries))
        self.load_queue()

    def add(self, entity: str):
        if not (ENTITY_DIR / f"{entity}.jpg").exists():
            log.error(f"Entity [bold red]{entity}[/] does not exist.")
        elif entity in self.entries:
            log.warning(
                f"Entity [bold yellow]{entity}[/] already exists in the [cyan]{self.key}[/] queue."
            )
        elif not self.key:
            log.error("No key is given to update the queue.")
        else:
            self.entries.append(entity)
            self.update()
            log.info(
                f"Entity [bold blue]{entity}[/] is added to the [cyan]{self.key}[/] queue."
            )
            return True

    def remove(self, entity: str):  # type: ignore
        if entity in self.entries:
            self.entries.remove(entity)
            self.update()
            log.info(
                f"Entity [bold blue]{entity}[/] has been removed from the [cyan]{self.key}[/] queue."
            )
        else:
            log.error(
                f"Entity [bold red]{entity}[/] does not exists in the [cyan]{self.key}[/] queue."
            )

    @staticmethod
    def dir_exists(entity: str) -> bool:
        return any(subdir for subdir in IA_DIR.rglob(entity))


FOLLOW_QUEUE = Queue(FOLLOW_QUEUE_DIR, "FOLLOW_QUEUE", Queue.Order.COUNT)
SCRAPE_QUEUE = Queue(SCRAPE_QUEUE_DIR, "SCRAPE_QUEUE", Queue.Order.COUNT)
