"""A flow that classifies all the scanned entities based on gender."""

from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.postgres import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.tasks.ollama import classify, get_gc_client
from insta_automate.vars import GENDER_INVALID_DIR, GENDER_VALID_DIR, SCANNED_DIR


@ia_flow()
async def gender_classify():
    log = get_run_logger()
    gc = get_gc_client()
    session = SessionLocal()
    started_at = Timestamp()
    batch, total = 0, 0
    GENDER_VALID_DIR.mkdir(parents=True, exist_ok=True)
    GENDER_INVALID_DIR.mkdir(parents=True, exist_ok=True)
    while list(SCANNED_DIR.glob("*.jpg")):
        batch += 1
        log.info(f"--- BATCH {batch} ---")
        total += classify(gc, session)
    if total == 0:
        log.error("No entities found to process")
        return
    else:
        time_taken = Timestamp() - started_at
        log.info(
            f"Gender classification complete. Total entities processed: {total} at {total / time_taken.total_seconds():.3} img/s rate. Time taken: {time_taken}"
        )


if __name__ == "__main__":
    gender_classify.serve()
