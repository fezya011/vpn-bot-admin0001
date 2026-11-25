from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    admin_ids: list[int]
    protected_containers: list[str] = []
    allow_host_reboot: bool = False
    self_container: str = "admin-bot"

    monitor_interval: int = 60
    ram_alert_percent: int = 90
    disk_alert_percent: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
