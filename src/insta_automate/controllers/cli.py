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
from telethon.types import Channel
from typer import Option

from insta_automate.controllers.telegram import IaTelegramClient
from insta_automate.vars import (
    BANNER,
    IA_BACKUP_CHANNEL,
    IA_DATABASE,
    IA_ENTITY_CHANNEL,
    IA_IMAGE,
    IA_NOTIFY_CHANNEL,
)

log = get_logger(__name__)
print(BANNER)

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
    if await tl.start_(timeout=timeout):
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


@tl.async_command(
    name="init", help="Initialize Telegram session and channels for Insta Automate."
)
async def tl_init():
    def channel_str(channel: Channel) -> str:
        return f"Channel(id={channel.id}, title='{channel.title}')"

    started_at = now()

    tl = IaTelegramClient()
    await tl.start()
    if channel := await tl.get_channel(IA_ENTITY_CHANNEL, strict=False):
        log.info(f"Entity channel found: {channel_str(channel)}")
    else:
        log.error("Entity channel not found. Creating one...")
        channel = await tl.create_channel(
            IA_ENTITY_CHANNEL, about="Insta Automate Entity Channel", broadcast=False
        )
        log.info(f"Entity channel created: {channel_str(channel)}")
    if channel := await tl.get_channel(IA_BACKUP_CHANNEL, strict=False):
        log.info(f"Backup channel found: {channel_str(channel)}")
    else:
        log.error("Backup channel not found. Creating one...")
        channel = await tl.create_channel(
            IA_BACKUP_CHANNEL, about="Insta Automate Backup Channel", broadcast=True
        )
        log.info(f"Backup channel created: {channel_str(channel)}")
    if channel := await tl.get_channel(IA_NOTIFY_CHANNEL, strict=False):
        log.info(f"Notify channel found: {channel_str(channel)}")
    else:
        log.error("Notify channel not found. Creating one...")
        channel = await tl.create_channel(
            IA_NOTIFY_CHANNEL, about="Insta Automate Notify Channel", broadcast=True
        )
        log.info(f"Notify channel created: {channel_str(channel)}")

    log.info(f"Telegram initialization complete. Time taken: {now() - started_at}")
