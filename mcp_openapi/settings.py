from pydantic_core import Url
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_OPENAPI_")

    openapi_url: Url
