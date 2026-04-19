from my_modules.postgres import PostgresSecret
from my_modules.win32 import get_wsl_host_ip
from pydantic import BaseModel

from insta_automate.vars import (
    ADB_SERVER_SOCKET,
    ANDROID_PIN,
    ANDROID_SERIAL,
    GIT_URL,
    IA_ALT_ACCOUNT,
    IA_DATABASE,
    IA_MAIN_ACCOUNT,
    IA_PREFECT_WORKPOOL,
)


class DockerEnv(BaseModel):
    SQLALCHEMY_CONN_URL: str = PostgresSecret.get_connection_string(
        database=IA_DATABASE, local=False
    )
    ADB_SERVER_SOCKET: str = ADB_SERVER_SOCKET
    ANDROID_PIN: str = ANDROID_PIN
    ANDROID_SERIAL: str = ANDROID_SERIAL
    GIT_URL: str = GIT_URL
    IA_ALT_ACCOUNT: str = IA_ALT_ACCOUNT
    IA_MAIN_ACCOUNT: str = IA_MAIN_ACCOUNT
    IA_PREFECT_WORKPOOL: str = IA_PREFECT_WORKPOOL
    WINDOWS_HOST: str = get_wsl_host_ip()
    TZ: str = "Asia/Kolkata"

    def model_dump_env(self) -> list[str]:
        return [f"ENV {key}='{value}'" for key, value in self.model_dump().items()]
