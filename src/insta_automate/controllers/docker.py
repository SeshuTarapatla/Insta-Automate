from importlib.metadata import version
from pathlib import Path
from subprocess import run
from sys import version_info

from my_modules.datetime_utils import now
from my_modules.git import Git
from my_modules.logger import get_logger
from my_modules.postgres import PostgresSecret
from my_modules.win32 import get_wsl_host_ip
from prefect_k3s.vars import PREFECT_IMAGE

from insta_automate.vars import ADB_DEVICE_SERIAL, IA_DATABASE

log = get_logger(__name__)


class IaDocker:
    @staticmethod
    def build(prefix: str):
        from tg_auth import TelegramSecret

        started_at = now()

        python_version = f"{version_info.major}.{version_info.minor}"
        prefect_version = version("prefect")
        tag = f"{prefect_version}-python{python_version}"
        base_image = f"{PREFECT_IMAGE}:{tag}"
        custom_image = f"{prefix}:{tag}"

        sqlalchemy_conn_url = PostgresSecret.get_connection_string(
            database=IA_DATABASE, local=False
        )

        git = Git()

        log.info(f"Current python version: {python_version}")
        log.info(f"Prefect version installed: {prefect_version}")
        log.info(f"Base Image: '{base_image}'")
        log.info(f"Building custom image with dependencies injected: '{custom_image}'")

        dockerfile = Path("Dockerfile")
        dockefile_contents = "\n".join(
            (
                f"FROM {base_image}",
                "",
                f"ENV SQLALCHEMY_CONN_URL={sqlalchemy_conn_url}",
                f"ENV WINDOWS_HOST={get_wsl_host_ip()}",
                f"ENV ADB_DEVICE_SERIAL={ADB_DEVICE_SERIAL}",
                *TelegramSecret.get().model_dump_env(),
                "",
                f"RUN uv pip install git+{git.remote_url}@{git.current_branch}",
            )
        )
        dockerfile.write_text(dockefile_contents)
        run(["docker", "build", "--no-cache", "-t", custom_image, "."])
        log.info(f"Build complete. Time taken: {now() - started_at}")
