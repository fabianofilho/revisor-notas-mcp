"""As duas tools: validar a nota e anotar correções."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from revisor_notas_mcp.llm.checagem_semantica import checar
from revisor_notas_mcp.llm.qwen_client import EndpointNaoLocal, QwenClient
from revisor_notas_mcp.parser.soap import SECOES, parse
from revisor_notas_mcp.rules.checklist import Problema, validar

logger = logging.getLogger(__name__)


class RespostaValidacao(BaseModel):
    """Resultado da validação de uma nota."""

    total_erros: int
    total_avisos: int
    problemas: list[Problema]
    checagem_semantica_feita: bool = Field(
        description="False quando o LLM local não respondeu; as regras valeram assim mesmo"
    )
    motivo_semantica_pulada: str | None = None
    aviso: str | None = None


class RespostaCorrecoes(BaseModel):
    """A nota com anotações inline, sem reescrever o texto original."""

    nota_anotada: str
    total_anotacoes: int
    checagem_semantica_feita: bool
    aviso: str | None = None


AVISO_SEMANTICA = (
    "As checagens de coerência e de sinais de alarme são feitas por um LLM local e são "
    "probabilísticas: leia como sugestão de revisão, não como veredito clínico."
)
AVISO_SEM_LLM = (
    "O LLM local não respondeu, então só as regras determinísticas rodaram. "
    "Coerência e sinais de alarme não foram checados."
)


async def _problemas(
    texto_nota: str,
    *,
    qwen_endpoint: str,
    qwen_model: str,
    timeout_segundos: float,
    usar_llm: bool,
) -> tuple[list[Problema], bool, str | None]:
    """Regras sempre; semântica quando o LLM local estiver disponível."""
    nota = parse(texto_nota)
    encontrados = validar(nota)

    if not usar_llm:
        return encontrados, False, "checagem semântica desligada nesta chamada"

    try:
        async with QwenClient(
            qwen_endpoint, qwen_model, timeout_segundos=timeout_segundos
        ) as cliente:
            if not await cliente.esta_vivo():
                return encontrados, False, "LLM local não respondeu"
            semanticos, motivo = await checar(cliente, nota)
    except EndpointNaoLocal:
        # Configuração perigosa: não é para degradar em silêncio.
        raise
    except Exception as erro:  # noqa: BLE001 - nenhuma falha pode derrubar a validação
        logger.warning("checagem semântica falhou: %s", type(erro).__name__)
        return encontrados, False, f"checagem semântica falhou: {type(erro).__name__}"

    if motivo is not None:
        return encontrados, False, motivo
    return [*encontrados, *semanticos], True, None


async def validar_nota_soap(
    texto_nota: str,
    *,
    qwen_endpoint: str,
    qwen_model: str,
    timeout_segundos: float = 15.0,
    usar_llm: bool = True,
) -> RespostaValidacao:
    """Valida uma nota SOAP e devolve os problemas encontrados."""
    if not texto_nota.strip():
        return RespostaValidacao(
            total_erros=1,
            total_avisos=0,
            problemas=[Problema(secao="nota", severidade="erro", descricao="Nota vazia.")],
            checagem_semantica_feita=False,
        )

    problemas, semantica_feita, motivo = await _problemas(
        texto_nota,
        qwen_endpoint=qwen_endpoint,
        qwen_model=qwen_model,
        timeout_segundos=timeout_segundos,
        usar_llm=usar_llm,
    )
    return RespostaValidacao(
        total_erros=sum(1 for p in problemas if p.severidade == "erro"),
        total_avisos=sum(1 for p in problemas if p.severidade == "aviso"),
        problemas=problemas,
        checagem_semantica_feita=semantica_feita,
        motivo_semantica_pulada=motivo,
        aviso=AVISO_SEMANTICA if semantica_feita else AVISO_SEM_LLM,
    )


async def sugerir_correcoes(
    texto_nota: str,
    *,
    qwen_endpoint: str,
    qwen_model: str,
    timeout_segundos: float = 15.0,
    usar_llm: bool = True,
) -> RespostaCorrecoes:
    """Devolve a nota com anotações inline. Não reescreve o texto original."""
    problemas, semantica_feita, _ = await _problemas(
        texto_nota,
        qwen_endpoint=qwen_endpoint,
        qwen_model=qwen_model,
        timeout_segundos=timeout_segundos,
        usar_llm=usar_llm,
    )

    por_secao: dict[str, list[Problema]] = {}
    for problema in problemas:
        por_secao.setdefault(problema.secao, []).append(problema)

    linhas: list[str] = []
    for linha in texto_nota.splitlines():
        linhas.append(linha)
        marcador = linha.strip().lstrip("-").strip()[:1].upper()
        if marcador in SECOES:
            for problema in por_secao.get(marcador, []):
                marca = "ERRO" if problema.severidade == "erro" else "AVISO"
                sufixo = f" → {problema.sugestao}" if problema.sugestao else ""
                linhas.append(f"    <<{marca}: {problema.descricao}{sufixo}>>")

    gerais = por_secao.get("nota", [])
    if gerais:
        linhas.insert(0, "<<PROBLEMAS NO DOCUMENTO>>")
        for indice, problema in enumerate(gerais, start=1):
            linhas.insert(indice, f"    <<{problema.severidade.upper()}: {problema.descricao}>>")

    return RespostaCorrecoes(
        nota_anotada="\n".join(linhas),
        total_anotacoes=len(problemas),
        checagem_semantica_feita=semantica_feita,
        aviso=AVISO_SEMANTICA if semantica_feita else AVISO_SEM_LLM,
    )
