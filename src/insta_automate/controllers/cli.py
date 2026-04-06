__all__ = ["ia"]

from async_typer import AsyncTyper
from my_modules.logger import get_logger
from typer import Option

from insta_automate.controllers.docker import IaDocker
from insta_automate.controllers.postgres import IaPostgres
from insta_automate.controllers.prefect import Prefect
from insta_automate.controllers.telegram import IaTelegram
from insta_automate.vars import (
    BANNER,
    IA_IMAGE,
)

log = get_logger(__name__)
print(BANNER)

ia = AsyncTyper(
    name="ia", help="Insta Automate CLI.", add_completion=False, no_args_is_help=True
)
tl = AsyncTyper(
    name="tl", help="Insta Automate telegram commands.", no_args_is_help=True
)
db = AsyncTyper(
    name="db", help="Insta Automate database commands.", no_args_is_help=True
)
prefect = AsyncTyper(name="prefect", help="Insta Automate Prefect flow scheduler.")
[ia.add_typer(subcommand) for subcommand in [tl, db, prefect]]


@ia.command(name="build", help="Build [magenta]Insta-Automate[/] docker image.")
def ia_build(prefix: str = IA_IMAGE):
    IaDocker.build(prefix)


@tl.async_command(
    name="verify", help="Verify telegram user and bot session from environment."
)
async def tl_verify(
    timeout: float = Option(
        2, "-t", "--timeout", help="Timeout for session verification."
    ),
):
    await IaTelegram.verify()


@tl.async_command(
    name="init", help="Initialize Telegram session and channels for Insta Automate."
)
async def tl_init():
    await IaTelegram.init()


@db.command(name="init", help="Initialize Insta Automate PostgreSQL database & tables.")
def db_init(
    drop: bool = Option(
        False, "-d", "--drop", help="Drop existing database & create a new one."
    ),
):
    IaPostgres.init(drop=drop)


@prefect.async_command(
    name="serve", help="Serve Prefect triggerer and scheduler for Insta Automate flows."
)
async def prefect_serve():
    await Prefect().serve()
