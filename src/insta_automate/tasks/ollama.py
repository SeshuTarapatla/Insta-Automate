from shutil import move

from prefect import get_run_logger
from sqlmodel import Session

from insta_automate.controllers.ollama import GenderClassifier
from insta_automate.models.meta import Gender
from insta_automate.models.scanned import Scanned
from insta_automate.tasks import ia_task
from insta_automate.vars import (
    GENDER_INVALID_DIR,
    GENDER_VALID_DIR,
    OLLAMA_VL_MODEL,
    SCANNED_DIR,
)


@ia_task()
def get_gc_client() -> GenderClassifier:
    log = get_run_logger()
    log.info(
        f"Creating a GenderClassifier client and loading {OLLAMA_VL_MODEL} model into GPU."
    )
    return GenderClassifier(OLLAMA_VL_MODEL)


@ia_task()
def classify(gc: GenderClassifier, session: Session) -> int:
    log = get_run_logger()
    entities = list(SCANNED_DIR.glob("*.jpg"))
    total = len(entities)
    for i, entity in enumerate(entities, start=1):
        scanned = Scanned.fetch(entity.stem, session)
        scanned.gender = gc.predict(entity).result
        log.info(f"[{i / total:.2%}] {i}/{total}. @{scanned.id}: {scanned.gender.upper()}")
        session.merge(scanned)
        session.commit()
        match scanned.gender:
            case Gender.FEMALE:
                move(entity, GENDER_VALID_DIR)
            case Gender.MALE:
                move(entity, GENDER_INVALID_DIR)
            case _:
                log.error(f"Failed to predict gender of @{scanned.id}")
    return total
