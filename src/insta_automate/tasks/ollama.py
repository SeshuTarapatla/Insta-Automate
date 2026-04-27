from typing import TypeVar

from prefect import get_run_logger
from sqlmodel import Session

from insta_automate.controllers.ollama import (
    AccessClassifier,
    AiClassifier,
    GenderClassifier,
)
from insta_automate.controllers.prefect import IaSession
from insta_automate.models.meta import EntityAccess, Gender
from insta_automate.models.scanned import Scanned
from insta_automate.tasks import ia_task
from insta_automate.utils import move
from insta_automate.vars import (
    GENDER_INVALID_DIR,
    GENDER_VALID_DIR,
    OLLAMA_VL_MODEL,
    SCANNED_DIR,
)

T = TypeVar("T", bound=AiClassifier)


@ia_task()
def get_ai_client(classifier: type[T]) -> T:
    log = get_run_logger()
    log.info(
        f"Creating a {classifier.__name__} client and loading {OLLAMA_VL_MODEL} model into GPU."
    )
    return classifier()


@ia_task()
def remove_public(session: Session | None = None) -> tuple[int, int, int]:
    log = get_run_logger()
    session = session or IaSession()
    classifier = get_ai_client(AccessClassifier)
    entities = list(SCANNED_DIR.glob("*.jpg"))

    total, public, private, failed = len(entities), 0, 0, 0

    for i, entity in enumerate(entities, start=1):
        scanned = Scanned.fetch(entity.stem, session)
        scanned.access = classifier.predict(entity).result
        log.info(
            f"[{i / total:.2%}] {i}/{total}. @{scanned.id}: {scanned.access.upper()}"
        )
        session.merge(scanned)
        session.commit()
        match scanned.access:
            case EntityAccess.PRIVATE:
                private += 1
            case EntityAccess.PUBLIC:
                public += 1
                entity.unlink()
            case _:
                failed += 1
                log.error(f"Failed to predict access of @{scanned.id}")
    log.info(
        f"Total entities parsed: {total}. Stats: PRIVATE={private}, PUBLIC={public}, FAILED={failed}"
    )
    return private, public, total


@ia_task()
def gender_classify(session: Session | None = None) -> tuple[int, int, int]:
    log = get_run_logger()
    session = session or IaSession()
    classifier = get_ai_client(GenderClassifier)
    entities = list(SCANNED_DIR.glob("*.jpg"))

    GENDER_VALID_DIR.mkdir(exist_ok=True, parents=True)
    GENDER_INVALID_DIR.mkdir(exist_ok=True, parents=True)
    total, male, female, failed = len(entities), 0, 0, 0

    for i, entity in enumerate(entities, start=1):
        scanned = Scanned.fetch(entity.stem, session)
        scanned.gender = classifier.predict(entity).result
        log.info(
            f"[{i / total:.2%}] {i}/{total}. @{scanned.id}: {scanned.gender.upper()}"
        )
        session.merge(scanned)
        session.commit()
        match scanned.gender:
            case Gender.FEMALE:
                female += 1
                move(entity, GENDER_VALID_DIR / entity.name, replace=True)
            case Gender.MALE:
                male += 1
                move(entity, GENDER_INVALID_DIR / entity.name, replace=True)
            case _:
                failed += 1
                log.error(f"Failed to predict gender of @{scanned.id}")
    log.info(
        f"Total entities parsed: {total}. Stats: FEMALE={female}, MALE={male}, FAILED={failed}"
    )
    return female, male, total
