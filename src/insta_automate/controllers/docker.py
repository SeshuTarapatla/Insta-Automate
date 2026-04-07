from importlib.metadata import version
from pathlib import Path
from subprocess import run
from sys import version_info

from my_modules.datetime_utils import now
from my_modules.git import Git
from my_modules.logger import get_logger
from prefect_k3s.vars import PREFECT_IMAGE

from insta_automate.models.docker import DockerEnv

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
                *DockerEnv().model_dump_env(),
                *TelegramSecret.get().model_dump_env(),
                "",
                f"RUN uv pip install git+{git.remote_url}@{git.current_branch}",
            )
        )
        dockerfile.write_text(dockefile_contents)
        run(["docker", "build", "--no-cache", "-t", custom_image, "."])
        log.info(f"Build complete. Time taken: {now() - started_at}")
