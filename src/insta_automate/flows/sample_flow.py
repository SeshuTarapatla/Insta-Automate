import asyncio

from insta_automate.flows import named_flow

description: str = "Sample flow to test Prefect functionality."


@named_flow()
async def sample_flow():
    await asyncio.sleep(3000)
