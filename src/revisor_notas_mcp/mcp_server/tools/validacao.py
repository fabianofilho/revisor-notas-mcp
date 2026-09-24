"""As duas tools: validar a nota e anotar correções."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from revisor_notas_mcp.llm.checagem_semantica import checar
from revisor_notas_mcp.llm.qwen_client import EndpointNaoLocal, QwenClient
from revisor_notas_mcp.parser.soap import SECOES, letra_do_marcador, parse
from revisor_notas_mcp.rules.checklist import Problema, validar

logger = logging.getLogger(__name__)


class RespostaValidacao(BaseModel):
    """Resultado da validação de uma nota."""

    total_erros: int
    total_avisos: int
    problemas: list[Problema]
    checagem_semantica_feita: bool = Field(
        description=(
            "False quando a semântica não rodou (motivo em motivo_semantica_pulada); "
            "as regras valeram assim mesmo"
        )
    )
    motivo_semantica_pulada: str | None = None
    aviso: str | None = None


class RespostaCorrecoes(BaseModel):
    """A nota com anotações inline, sem reescrever o texto original."""

    nota_anotada: str
    total_anotacoes: int = Field(description="Número de problemas; cada um aparece uma vez")
    checagem_semantica_feita: bool
    motivo_semantica_pulada: str | None = None
    aviso: str | None = None


AVISO_SEMANTICA = (
    "As checagens de coerência e de sinais de alarme são feitas por um LLM local e são "
    "probabilísticas: leia como sugestão de revisão, não como veredito clínico."
)
AVISO_SEM_LLM = (
    "A checagem semântica não rodou ({motivo}), então só as regras determinísticas "
    "valeram. Coerência e sinais de alarme não foram checados."
)


NOTA_VAZIA = Problema(secao="nota", severidade="erro", descricao="Nota vazia.")


def _aviso(semantica_feita: bool, motivo: str | None) -> str:
    """O aviso diz o motivo real, em vez de culpar sempre o LLM."""
    if semantica_feita:
        return AVISO_SEMANTICA
    return AVISO_SEM_LLM.format(motivo=motivo or "motivo não informado")


def _letras(secao: str) -> list[str]:
    """'F, A, P', 'a', 'A: Avaliação' viram letras de seção; 'nota' vira lista vazia."""
    letras: list[str] = []
    for parte in secao.split(","):
        letra = parte.strip().lstrip("-\u2013\u2014").strip()[:1].upper()
        if parte.strip().lower() != "nota" and letra in SECOES and letra not in letras:
            letras.append(letra)
    return letras


def _formatar(problema: Problema, *, com_secao: bool = False) -> str:
    marca = "ERRO" if problema.severidade == "erro" else "AVISO"
    rotulo = f" [{problema.secao}]" if com_secao else ""
    sufixo = f" → {problema.sugestao}" if problema.sugestao else ""
    return f"    <<{marca}{rotulo}: {problema.descricao}{sufixo}>>"


def anotar(texto_nota: str, problemas: list[Problema]) -> str:
    """Insere cada problema uma única vez, sem alterar nenhuma linha original.

    O problema vai para o fim da primeira seção que ele cita e que existe na nota
    (mesmo critério de marcador do parser). O que não tem seção na nota (seção
    ausente, problema do documento, seção que o LLM devolveu fora do padrão) vai
    para o bloco <<PROBLEMAS NO DOCUMENTO>> no topo, para nada se perder.
    """
    linhas = texto_nota.splitlines()
    marcadores = [(i, letra_do_marcador(linha)) for i, linha in enumerate(linhas)]
    inicios = [i for i, letra in marcadores if letra is not None]

    # Fim de cada seção: a linha antes do próximo marcador, ignorando linhas em branco.
    fim_da_secao: dict[str, int] = {}
    for posicao, (inicio, letra) in enumerate((i, x) for i, x in marcadores if x is not None):
        if letra in fim_da_secao:
            continue  # marcador repetido: vale o primeiro, como no parser
        proximo = inicios[posicao + 1] if posicao + 1 < len(inicios) else len(linhas)
        fim = proximo - 1
        while fim > inicio and not linhas[fim].strip():
            fim -= 1
        fim_da_secao[letra] = fim

    abaixo_de: dict[int, list[Problema]] = {}
    gerais: list[Problema] = []
    for problema in problemas:
        presentes = [letra for letra in _letras(problema.secao) if letra in fim_da_secao]
        if presentes:
            abaixo_de.setdefault(fim_da_secao[presentes[0]], []).append(problema)
        else:
            gerais.append(problema)

    saida: list[str] = []
    if gerais:
        saida.append("<<PROBLEMAS NO DOCUMENTO>>")
        saida.extend(_formatar(p, com_secao=p.secao != "nota") for p in gerais)
    for indice, linha in enumerate(linhas):
        saida.append(linha)
        for problema in abaixo_de.get(indice, []):
            saida.append(_formatar(problema, com_secao=len(_letras(problema.secao)) > 1))
    return "\n".join(saida)


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
            problemas=[NOTA_VAZIA],
            checagem_semantica_feita=False,
            motivo_semantica_pulada="nota vazia",
            aviso=_aviso(False, "nota vazia"),
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
        aviso=_aviso(semantica_feita, motivo),
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
    if not texto_nota.strip():
        return RespostaCorrecoes(
            nota_anotada=anotar(texto_nota, [NOTA_VAZIA]),
            total_anotacoes=1,
            checagem_semantica_feita=False,
            motivo_semantica_pulada="nota vazia",
            aviso=_aviso(False, "nota vazia"),
        )

    problemas, semantica_feita, motivo = await _problemas(
        texto_nota,
        qwen_endpoint=qwen_endpoint,
        qwen_model=qwen_model,
        timeout_segundos=timeout_segundos,
        usar_llm=usar_llm,
    )

    return RespostaCorrecoes(
        nota_anotada=anotar(texto_nota, problemas),
        total_anotacoes=len(problemas),
        checagem_semantica_feita=semantica_feita,
        motivo_semantica_pulada=motivo,
        aviso=_aviso(semantica_feita, motivo),
    )
