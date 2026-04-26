from my_modules.datetime_utils import Timestamp
from prefect import get_run_logger

from insta_automate.controllers.prefect import SessionLocal
from insta_automate.flows import ia_flow
from insta_automate.tasks.ollama import remove_public, gender_classify
from insta_automate.vars import SCANNED_DIR


@ia_flow()
def ai_classify():
    log = get_run_logger()
    started_at = Timestamp()
    session = SessionLocal()
    images = list(SCANNED_DIR.glob("*.jpg"))
    if images:
        log.info(f"Total entities to classify: {len(images)}")
        private, public, rtotal = remove_public(session)
        female, male, gtotal = gender_classify(session)
        total = rtotal + gtotal
        time_taken = Timestamp() - started_at
        log.info(
            f"AI classification complete. Total entities processed: {total} at {total / (time_taken.total_seconds() or 1):.3} img/s rate. Time taken: {time_taken}. Entities removed: {public}"
        )
    else:
        log.error("No entities found to classify")


if __name__ == "__main__":
    ai_classify.serve()
