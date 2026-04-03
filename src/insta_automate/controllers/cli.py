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
from typer import Option

from insta_automate.controllers.telegram import IaTelegramClient
from insta_automate.vars import IA_DATABASE, IA_IMAGE

log = get_logger(__name__)

ia = AsyncTyper(help="Insta Automate CLI.", add_completion=False, no_args_is_help=True)
tl = AsyncTyper(
    name="tl", help="Insta Automate telegram commands.", no_args_is_help=True
)

ia.add_typer(tl)


@ia.command(name="build", help="Build [magenta]Insta-Automate[/] docker image.")
def ia_build(prefix: str = IA_IMAGE):
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
            *TelegramSecret.get().model_dump_env(),
            f"RUN uv pip install git+{git.remote_url}@{git.current_branch}",
        )
    )
    dockerfile.write_text(dockefile_contents)
    run(["docker", "build", "--no-cache", "-t", custom_image, "."])
    log.info(f"Build complete. Time taken: {now() - started_at}")


@tl.async_command(
    name="verify", help="Verify telegram user and bot session from environment."
)
async def tl_verify(
    timeout: float = Option(
        2, "-t", "--timeout", help="Timeout for session verification."
    ),
):
    tl, exit_code = IaTelegramClient(), 0
    if await tl.start(timeout=timeout):
        log.info("Telegram User session: [dim green]CONNECTED![/]")
    else:
        log.error("Telegram User session: [dim red]DISCONNECTED![/]")
        exit_code = 1
    if await tl.bot.start(timeout=timeout):
        log.info("Telegram Bot  session: [dim green]CONNECTED![/]")
    else:
        log.error("Telegram Bot  session: [dim red]DISCONNECTED![/]")
        exit_code = 1
    exit(exit_code)
