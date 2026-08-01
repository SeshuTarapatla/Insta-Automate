"""A flow that ingests all the entities from Insta Automate Entity channel."""

from prefect import get_run_logger
from pydantic import ValidationError

from insta_automate.controllers.agent import AgentClient
from insta_automate.controllers.instagram import Insta
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.flows import ia_flow
from insta_automate.tasks.data import db_backup
from insta_automate.tasks.device import device_ready
from insta_automate.tasks.ia import add_new_entity, append_entity_to_queue
from insta_automate.utils import rm_empty_subdirs
from insta_automate.vars import ENTITY_DIR


@ia_flow()
async def entity_ingest():
    log = get_run_logger()
    agent = AgentClient()
    await agent.emit({"flow": "entity-ingest", "kind": "flow.started"})
    tl = await IaTelegram.get_client()
    device = await device_ready(tl)
    entity = None
    processed = 0

    ENTITY_DIR.mkdir(exist_ok=True, parents=True)

    async for msg in tl.iter_entity_messages():
        text = str(msg.text)
        try:
            if text.startswith(Insta.URL):
                entity = await add_new_entity(text, device, tl)
                processed += 1
            else:
                append_entity_to_queue(text)
        except ValidationError:
            log.error(f"Message(text='{text}') is not a valid entity url.")
        await tl.delete_message(msg)

    if entity:
        rm_empty_subdirs()
        device.lock()
        await db_backup()
    else:
        log.error("No entities found to ingest.")
    await agent.emit({
        "flow": "entity-ingest", "kind": "flow.completed",
        "counters": {"processed": processed},
    })


if __name__ == "__main__":
    entity_ingest.serve()
