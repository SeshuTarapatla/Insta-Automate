"""A flow that ingests all the entities from Insta Automate Entity channel."""

from prefect import get_run_logger
from pydantic import ValidationError

from insta_automate.controllers.cli import append_entity
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.flows import ia_flow
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready
from insta_automate.tasks.ia import add_new_entity
from insta_automate.utils import rm_empty_subdirs
from insta_automate.vars import ENTITY_DIR


@ia_flow()
async def entity_ingest():
    log = get_run_logger()
    tl = await IaTelegram.get_client()
    device = await device_ready(tl)
    entity = None

    ENTITY_DIR.mkdir(exist_ok=True, parents=True)

    async for msg in tl.iter_entity_messages():
        try:
            text = str(msg.text)
            if (ENTITY_DIR / f"{text}.jpg").exists():
                entity = append_entity(str(text))
                match entity:
                    case -1:
                        entity = False
                        log.error(f"No entity exists with id: @{text}")
                    case 0:
                        entity = False
                        log.warning(f"Entity is already present in the queue: @{text}")
                    case 1:
                        entity = True
                        log.info(f"Entity added to the queue: @{text}")
            else:
                entity = add_new_entity(str(text), device)
        except ValidationError:
            log.error(f"Message(text='{msg.text}') is not a valid entity url.")
        await tl.delete_message(msg)

    if entity:
        rm_empty_subdirs()
        device.lock()
        await db_backup()
    else:
        log.error("No entities found to ingest.")


if __name__ == "__main__":
    entity_ingest.serve()
