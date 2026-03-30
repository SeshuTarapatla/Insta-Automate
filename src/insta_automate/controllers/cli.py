__all__ = ["ia"]

from importlib.metadata import version
from pathlib import Path
from subprocess import run
from sys import version_info

from async_typer import AsyncTyper
from my_modules.datetime_utils import now
from my_modules.git import Git
from my_modules.logger import get_logger
from my_modules.postgres import PostgresSecret
from prefect_k3s.vars import PREFECT_IMAGE

from insta_automate.vars import IA_IMAGE

log = get_logger(__name__)

ia = AsyncTyper(help="Insta Automate CLI.", add_completion=False, no_args_is_help=True)


@ia.command(name="build", help="Build [magenta]Insta-Automate[/] docker image.")
def ia_build(prefix: str = IA_IMAGE):
    started_at = now()
    python_version = f"{version_info.major}.{version_info.minor}"
    prefect_version = version("prefect")
    tag = f"{prefect_version}-python{python_version}"
    base_image = f"{PREFECT_IMAGE}:{tag}"
    custom_image = f"{prefix}:{tag}"
    sqlalchemy_conn_url = PostgresSecret.get_connection_string(local=False)

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
            f"RUN uv pip install git+{git.remote_url}@{git.current_branch}",
        )
    )
    dockerfile.write_text(dockefile_contents)
    run(["docker", "build", "--no-cache", "-t", custom_image, "."])
    log.info(f"Build complete. Time taken: {now() - started_at}")


@ia.command()
def nan(): ...
