"""Sample flow to test Prefect functionality."""

import asyncio

from prefect import get_run_logger

from insta_automate.flows import ia_flow


@ia_flow()
async def sample_flow(wait: float = 60):
    log = get_run_logger()
    log.info(f"Await for {wait} seconds.")
    await asyncio.sleep(wait)
    log.info("Sleep complete.")


if __name__ == "__main__":
    sample_flow.serve()
