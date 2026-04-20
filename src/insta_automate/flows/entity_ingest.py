"""A flow that ingests all the entities from Insta Automate Entity channel."""

from prefect import get_run_logger
from pydantic import ValidationError

from insta_automate.controllers.telegram import IaTelegram
from insta_automate.flows import ia_flow
# from insta_automate.tasks.db import db_backup
from insta_automate.tasks.ia import add_new_entity


@ia_flow()
async def entity_ingest():
    log = get_run_logger()
    tl = await IaTelegram.get_client()

    async for msg in tl.iter_entity_messages():
        try:
            add_new_entity(str(msg.text))
        except ValidationError:
            log.error(f"Message(text='{msg.text}') is not a valid entity url.")
        await tl.delete_message(msg)
    # await db_backup()
