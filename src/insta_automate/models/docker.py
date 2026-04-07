from my_modules.postgres import PostgresSecret
from my_modules.win32 import get_wsl_host_ip
from pydantic import BaseModel

from insta_automate.vars import (
    ADB_SERVER_SOCKET,
    ANDROID_PIN,
    ANDROID_SERIAL,
    IA_DATABASE,
)


class DockerEnv(BaseModel):
    SQLALCHEMY_CONN_URL: str = PostgresSecret.get_connection_string(
        database=IA_DATABASE, local=False
    )
    WINDOWS_HOST: str = get_wsl_host_ip()
    ADB_SERVER_SOCKET: str = ADB_SERVER_SOCKET
    ANDROID_SERIAL: str = ANDROID_SERIAL
    ANDROID_PIN: str = ANDROID_PIN

    def model_dump_env(self) -> list[str]:
        return [f"ENV {key}='{value}'" for key, value in self.model_dump().items()]
