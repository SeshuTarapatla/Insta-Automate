from typing import Literal

from prefect import get_run_logger, task

from insta_automate.controllers.device import IaDevice
from insta_automate.controllers.postgres import SessionLocal
from insta_automate.models.entity import Entity


@task
def switch_account(device: IaDevice, account: Literal["main", "alt"]) -> bool:
    log = get_run_logger()
    log.info(f"Switching to {account.upper()} account.")
    return device.switch_account(account)


@task
def add_new_entity(device: IaDevice, url: str) -> Entity:
    log = get_run_logger()
    log.info(f"Input entity url: {url}")
    entity = Entity.model_validate(Entity(url=url))
    with SessionLocal() as session:
        if (_entity := entity.fetch(session)) is not None:
            log.warning(f"Entity already exists: {_entity.model_dump_json(indent=4)}")
        else:
            switch_account(device, "alt")
            log.info(f"Entity type is determined to be: {entity.type.upper()}")
            log.info("Determing entity access type...")
            entity.access = device.determine_entity_access(entity)
            log.info(f"Entity access type id determined to be: {entity.access.upper()}")
            log.info(entity.model_dump_json(indent=4))
            log.info("Adding entry to Entity table.")
            session.add(entity)
            session.commit()
    return entity
