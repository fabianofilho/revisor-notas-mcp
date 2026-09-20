"""Cliente do LLM local. Única chamada de rede do projeto, e para localhost.

Sem retry longo: a checagem semântica tem que caber no tempo de resposta da tool.
Se o modelo não responder, a validação por regras segue valendo.

Este módulo nunca registra em log o texto enviado — é nota de paciente.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_JSON_NA_RESPOSTA = re.compile(r"\{.*\}", re.DOTALL)

_HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class LLMIndisponivel(RuntimeError):
    """O modelo local não respondeu, ou respondeu algo inutilizável."""


class EndpointNaoLocal(ValueError):
    """Endpoint configurado aponta para fora da máquina.

    Este projeto processa texto de paciente: mandá-lo para um host remoto seria
    exatamente o que a arquitetura existe para impedir.
    """


def exigir_endpoint_local(endpoint: str) -> str:
    """Recusa qualquer endpoint que não seja localhost."""
    host = urlparse(endpoint).hostname
    if host not in _HOSTS_LOCAIS:
        raise EndpointNaoLocal(
            f"QWEN_ENDPOINT aponta para {host!r}. Este projeto só fala com localhost: "
            "a nota do paciente não sai da máquina."
        )
    return endpoint


class QwenClient:
    """Chat completions contra o endpoint OpenAI-compatible local."""

    def __init__(
        self,
        endpoint: str,
        modelo: str,
        *,
        timeout_segundos: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._endpoint = exigir_endpoint_local(endpoint).rstrip("/")
        self._modelo = modelo
        self._timeout = timeout_segundos
        self._client = client
        self._client_proprio = client is None

    async def __aenter__(self) -> QwenClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._client is not None and self._client_proprio:
            await self._client.aclose()
            self._client = None

    async def esta_vivo(self) -> bool:
        """Nunca levanta: serve para degradar com graça."""
        try:
            resposta = await self._exigir_client().get(f"{self._endpoint}/models", timeout=3.0)
            return resposta.status_code == 200
        except httpx.HTTPError as erro:
            logger.warning("LLM local não respondeu: %s", erro)
            return False

    async def pedir_json(self, sistema: str, usuario: str) -> dict[str, Any]:
        """Uma chamada, resposta em JSON. Sem retry: o tempo é curto de propósito."""
        try:
            resposta = await self._exigir_client().post(
                f"{self._endpoint}/chat/completions",
                json={
                    "model": self._modelo,
                    "messages": [
                        {"role": "system", "content": sistema},
                        {"role": "user", "content": usuario},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 700,
                    "response_format": {"type": "json_object"},
                },
                timeout=self._timeout,
            )
            resposta.raise_for_status()
            conteudo = str(resposta.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as erro:
            # Sem o texto da nota na mensagem de erro.
            raise LLMIndisponivel(f"LLM local falhou: {type(erro).__name__}") from erro

        return self._parse(conteudo)

    @staticmethod
    def _parse(conteudo: str) -> dict[str, Any]:
        bruto = conteudo.strip()
        try:
            return dict(json.loads(bruto))
        except json.JSONDecodeError:
            pass
        achado = _JSON_NA_RESPOSTA.search(bruto)
        if achado is None:
            raise LLMIndisponivel("resposta do LLM não continha JSON")
        try:
            return dict(json.loads(achado.group(0)))
        except json.JSONDecodeError as erro:
            raise LLMIndisponivel("resposta do LLM não era JSON válido") from erro

    def _exigir_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("QwenClient precisa ser usado como 'async with'")
        return self._client
