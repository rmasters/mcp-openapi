from enum import Enum
from pydantic_core import Url
from pydantic_settings import BaseSettings, SettingsConfigDict

import logging


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_OPENAPI_")

    openapi_url: Url
    log_level: LogLevel = LogLevel.INFO
