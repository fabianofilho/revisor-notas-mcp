"""Configuração lida do ambiente (.env)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Só o necessário: este projeto não persiste nada."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qwen_endpoint: str = Field(default="http://127.0.0.1:11434/v1")
    qwen_model: str = Field(default="local-model")
    # Curto de propósito: a checagem semântica é um extra, não pode travar a tool.
    timeout_checagem_semantica_segundos: float = Field(default=15.0)
    log_level: str = Field(default="INFO")


def carregar_config() -> Config:
    return Config()
