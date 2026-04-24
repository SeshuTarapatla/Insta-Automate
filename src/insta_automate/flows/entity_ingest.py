"""A flow that ingests all the entities from Insta Automate Entity channel."""

from prefect import get_run_logger
from pydantic import ValidationError

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.flows import ia_flow
from insta_automate.tasks.data import ia_backup
from insta_automate.tasks.ia import add_new_entity


@ia_flow()
async def entity_ingest():
    log = get_run_logger()
    tl = await IaTelegram.get_client()
    device = IaDevice()
    entity = None

    async for msg in tl.iter_entity_messages():
        try:
            entity = add_new_entity(str(msg.text), device)
        except ValidationError:
            log.error(f"Message(text='{msg.text}') is not a valid entity url.")
        await tl.delete_message(msg)

    if entity:
        device.lock()
        await ia_backup()
    else:
        log.error("No entities found to ingest.")


if __name__ == "__main__":
    entity_ingest.serve()
