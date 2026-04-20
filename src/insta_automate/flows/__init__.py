import asyncio
from importlib import import_module
from pkgutil import iter_modules
from typing import cast

from my_modules.datetime_utils import Timestamp
from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from prefect import Flow, flow
from prefect.runner.storage import GitRepository
from prefect.runtime import flow_run

from insta_automate.utils import set_logger_propagation
from insta_automate.vars import GIT_URL, IA_PREFECT_WORKPOOL

log = get_logger(__name__)


def ia_flow(
    *args,
    flow_run_name=lambda: f"{flow_run.flow_name}-{Timestamp().strftime('hyphen')}",
    retries: int | None = 3,
    retry_delay_seconds: int | None = 30,
    **kwargs,
):
    set_logger_propagation()
    return flow(
        *args,
        flow_run_name=flow_run_name,
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
        **kwargs,
    )


class IaFlows:
    @staticmethod
    async def deploy_all():
        src = GitRepository(url=GIT_URL)
        base = f"src/{__name__.replace('.', '/')}"
        for module in iter_modules(__path__):
            flow_name = module.name
            flow_ = import_module(f"{__name__}.{flow_name}")
            flow_path = f"{base}/{flow_name}.py:{flow_name}"
            flow_desc = (
                doc.strip() if (doc := flow_.__doc__) else "No description added."
            )
            deployment = flow_name.replace("_", "-")
            _flow = cast(Flow, await handle_await(flow.from_source(src, flow_path)))
            log.info(
                f"Deploying: Deployment(flow='{flow_name}', description='{flow_desc}')"
            )
            while True:
                try:
                    await handle_await(
                        _flow.deploy(
                            deployment,
                            work_pool_name=IA_PREFECT_WORKPOOL,
                            ignore_warnings=True,
                            description=flow_desc,
                            concurrency_limit=1,
                        )
                    )
                    break
                except Exception:
                    log.error(
                        f"Failed to deploy: '{flow_name}'. Retrying with delay..."
                    )
                    await asyncio.sleep(5)
