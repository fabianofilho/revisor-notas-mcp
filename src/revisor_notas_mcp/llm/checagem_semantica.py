"""Checagens que regra determinística não pega, feitas pelo LLM local.

Duas perguntas: (a) a queixa, o exame e a conduta são coerentes entre si;
(b) os sinais de alarme esperados para o diagnóstico foram investigados.

O texto da nota nunca é escrito em disco nem em log. Se o modelo não responder
no tempo, a checagem é pulada e a validação por regras responde sozinha.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from importlib.resources import files

from jinja2 import Environment, FunctionLoader, select_autoescape

from revisor_notas_mcp.llm.qwen_client import LLMIndisponivel, QwenClient
from revisor_notas_mcp.parser.soap import NotaSoap
from revisor_notas_mcp.rules.checklist import Problema

logger = logging.getLogger(__name__)


PACOTE_PROMPTS = "revisor_notas_mcp.prompts"


def _ler_prompt(nome: str) -> str | None:
    """Lê o template de dentro do pacote, para funcionar também instalado pelo wheel."""
    try:
        return files(PACOTE_PROMPTS).joinpath(nome).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None  # o jinja2 converte em TemplateNotFound


@lru_cache(maxsize=1)
def _ambiente() -> Environment:
    return Environment(
        loader=FunctionLoader(_ler_prompt),
        autoescape=select_autoescape(default=False, default_for_string=False),
    )


def _render(nome: str) -> str:
    return _ambiente().get_template(nome).render()


def _nota_em_texto(nota: NotaSoap) -> str:
    partes = [f"-{letra}: {nota.secao(letra)}" for letra in "FSOAP" if nota.secao(letra)]
    return "\n".join(partes)


async def checar_consistencia(cliente: QwenClient, nota: NotaSoap) -> list[Problema]:
    """Incoerências entre queixa, exame e conduta."""
    resposta = await cliente.pedir_json(_render("checar_consistencia.jinja2"), _nota_em_texto(nota))
    problemas: list[Problema] = []
    for item in resposta.get("incoerencias", []) or []:
        if not isinstance(item, dict):
            continue
        descricao = str(item.get("descricao", "")).strip()
        if not descricao:
            continue
        secoes = item.get("secoes") or []
        problemas.append(
            Problema(
                secao=", ".join(str(s) for s in secoes) if secoes else "nota",
                severidade="aviso",
                descricao=descricao,
                sugestao="Confira se a conduta corresponde à hipótese e ao que foi relatado.",
                origem="semantica",
            )
        )
    return problemas


async def checar_sinais_alarme(cliente: QwenClient, nota: NotaSoap) -> list[Problema]:
    """Sinais de alarme esperados para o diagnóstico que a nota não investigou."""
    if not (nota.a or "").strip():
        return []
    resposta = await cliente.pedir_json(
        _render("checar_sinais_alarme.jinja2"), _nota_em_texto(nota)
    )
    ausentes = [str(s).strip() for s in (resposta.get("ausentes") or []) if str(s).strip()]
    if not ausentes:
        return []
    return [
        Problema(
            secao="S",
            severidade="aviso",
            descricao=(
                "Sinais de alarme esperados para a hipótese que não aparecem como "
                f"investigados: {', '.join(ausentes)}."
            ),
            sugestao="Registre a investigação, mesmo que negativa ('nega ...').",
            origem="semantica",
        )
    ]


async def checar(cliente: QwenClient, nota: NotaSoap) -> tuple[list[Problema], str | None]:
    """Roda as duas checagens. Devolve os problemas e, se falhou, o motivo.

    Nunca levanta: a validação por regras precisa responder de qualquer jeito.
    """
    try:
        consistencia = await checar_consistencia(cliente, nota)
        alarme = await checar_sinais_alarme(cliente, nota)
    except LLMIndisponivel as erro:
        logger.warning("checagem semântica pulada: %s", erro)
        return [], str(erro)
    return [*consistencia, *alarme], None
