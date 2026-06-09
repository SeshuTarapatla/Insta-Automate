__all__ = ["ia_flow"]

import asyncio
from importlib import import_module
from pkgutil import iter_modules
from typing import TypedDict, cast

from my_modules.datetime_utils import Timestamp
from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from prefect import Flow, flow
from prefect.runner.storage import GitRepository
from prefect.runtime import flow_run

from insta_automate.utils import set_logger_propagation
from insta_automate.vars import (
    GIT_URL,
    IA_PREFECT_WORKPOOL,
)

log = get_logger(__name__)


class FlowDeployConfig(TypedDict, total=False):
    work_queue_name: str
    concurrency_limit: int | None


_DEPLOY_DEFAULTS: FlowDeployConfig = FlowDeployConfig(
    work_queue_name="standard",
    concurrency_limit=1,
)


def ia_flow(
    *args,
    flow_run_name=lambda: f"{flow_run.flow_name}-{Timestamp().strftime('hyphen')}",
    **kwargs,
):
    set_logger_propagation()
    return flow(
        *args,
        flow_run_name=flow_run_name,
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
            cfg = {**_DEPLOY_DEFAULTS, **getattr(flow_, "DEPLOY_CONFIG", {})}
            log.info(
                f"Deploying: Deployment(flow='{flow_name}', queue='{cfg['work_queue_name']}', description='{flow_desc}')"
            )
            while True:
                try:
                    await handle_await(
                        _flow.deploy(
                            deployment,
                            work_pool_name=IA_PREFECT_WORKPOOL,
                            ignore_warnings=True,
                            description=flow_desc,
                            **cfg,
                        )
                    )
                    break
                except Exception:
                    log.error(
                        f"Failed to deploy: '{flow_name}'. Retrying with delay..."
                    )
                    await asyncio.sleep(5)
