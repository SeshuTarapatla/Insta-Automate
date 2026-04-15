from importlib import import_module
from pkgutil import iter_modules

from my_modules.datetime_utils import Timestamp
from my_modules.helpers import handle_await
from my_modules.logger import get_logger
from prefect import Flow, flow
from prefect.runner.storage import GitRepository
from prefect.runtime import flow_run

from insta_automate.utils import set_logger_propagation
from insta_automate.vars import GIT_URL

log = get_logger(__name__)


def named_flow(
    *args,
    flow_run_name=lambda: f"{flow_run.flow_name}-{Timestamp().strftime('hyphen')}",
    **kwargs,
):
    set_logger_propagation()
    return flow(*args, flow_run_name=flow_run_name, **kwargs)


class IaFlows:
    @staticmethod
    async def deploy_all():
        src = GitRepository(url=GIT_URL)
        base = f"src/{__name__.replace('.', '/')}"
        for module in iter_modules(__path__):
            ia_flow_name = module.name
            ia_flow = import_module(f"{__name__}.{ia_flow_name}")
            ia_flow_path = f"{base}/{ia_flow_name}.py:{ia_flow_name}"
            ia_flow_description = ia_flow.description
            ia_deployment_name = ia_flow_name.replace("_", "-")
            log.info(f"{ia_flow_path, ia_flow_description, ia_deployment_name}")
            _flow = await handle_await(flow.from_source(src, ia_flow_path))
            log.info(type(_flow))
