"""Regras determinísticas sobre a nota SOAP.

Cada regra é uma função pura de ``NotaSoap`` para ``list[Problema]``, testável
isoladamente. Elas rodam sem LLM nenhum — se o modelo local estiver fora do ar, a
validação por regras continua valendo.

As regras seguem o template fixo da skill /clude.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field

Severidade = Literal["erro", "aviso"]

from revisor_notas_mcp.parser.soap import CABECALHO, NotaSoap  # noqa: E402

# CID-10: letra + 2 dígitos, com subcategoria opcional (J06.9, A09, M54.5)
_CID = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b")

RODAPE_CIENCIA = "Paciente ciente e concordante com plano terapêutico"
RODAPE_TELEMEDICINA = "Atendimento realizado via telemedicina"

# Campos que o template sempre traz dentro da seção S.
_CAMPOS_S = ("MUC:", "AP:", "AF:", "Alergia:", "Hábitos:")


class Problema(BaseModel):
    """Um achado da validação."""

    secao: str = Field(description="F, S, O, A, P ou 'nota' para problemas do documento inteiro")
    severidade: Severidade
    descricao: str
    sugestao: str | None = None
    origem: Literal["regra", "semantica"] = "regra"


def regra_cabecalho(nota: NotaSoap) -> list[Problema]:
    """A primeira linha precisa ser exatamente #TELEMEDICINA#."""
    if nota.cabecalho_presente:
        return []
    return [
        Problema(
            secao="nota",
            severidade="erro",
            descricao=f"Cabeçalho {CABECALHO} ausente na primeira linha.",
            sugestao=f"Comece a nota com {CABECALHO}.",
        )
    ]


def regra_secoes_obrigatorias(nota: NotaSoap) -> list[Problema]:
    """F, S, O, A e P precisam existir e ter conteúdo."""
    return [
        Problema(
            secao=letra,
            severidade="erro",
            descricao=f"Seção -{letra}: ausente ou vazia.",
            sugestao=f"Preencha a seção -{letra}: conforme o template.",
        )
        for letra in nota.secoes_ausentes
    ]


def regra_cid(nota: NotaSoap) -> list[Problema]:
    """A avaliação precisa trazer o CID, em formato válido."""
    avaliacao = nota.a or ""
    if not avaliacao.strip():
        return []
    if _CID.search(avaliacao):
        return []
    if "cid" in avaliacao.lower():
        return [
            Problema(
                secao="A",
                severidade="erro",
                descricao="CID mencionado mas fora do formato esperado (letra + 2 dígitos).",
                sugestao="Use o formato CID-10, por exemplo (CID: J06.9).",
            )
        ]
    return [
        Problema(
            secao="A",
            severidade="erro",
            descricao="Nenhum CID na hipótese diagnóstica.",
            sugestao="Acrescente o CID entre parênteses, por exemplo (CID: A09).",
        )
    ]


def regra_plano_numerado(nota: NotaSoap) -> list[Problema]:
    """O plano segue itens numerados de 1 a 5, sendo o 5 o do atestado."""
    plano = nota.p or ""
    if not plano.strip():
        return []

    problemas: list[Problema] = []
    numeros = {int(n) for n in re.findall(r"^\s*(\d)\.", plano, re.MULTILINE)}
    faltando = sorted({1, 2, 3, 4, 5} - numeros)
    if faltando:
        problemas.append(
            Problema(
                secao="P",
                severidade="aviso",
                descricao=f"Plano sem os itens numerados {faltando}.",
                sugestao="O template prevê os itens 1 a 5, sendo o 5 o do atestado.",
            )
        )
    if 5 in numeros and "atestado" not in plano.lower():
        problemas.append(
            Problema(
                secao="P",
                severidade="aviso",
                descricao="Item 5 do plano não menciona atestado.",
                sugestao="O item 5 declara o atestado emitido ou registra que não houve.",
            )
        )
    return problemas


def regra_sinais_alarme_no_plano(nota: NotaSoap) -> list[Problema]:
    """O plano precisa registrar que o paciente foi orientado sobre sinais de alarme."""
    plano = (nota.p or "").lower()
    if not plano.strip() or "sinais de alarme" in plano:
        return []
    return [
        Problema(
            secao="P",
            severidade="erro",
            descricao="Plano não registra orientação sobre sinais de alarme.",
            sugestao="Inclua o item 'Orientado sobre sinais de alarme: ...' com os do caso.",
        )
    ]


def regra_rodape(nota: NotaSoap) -> list[Problema]:
    """As duas frases finais do template são fixas e não podem sumir."""
    plano = nota.p or ""
    problemas: list[Problema] = []
    if RODAPE_CIENCIA.lower() not in plano.lower():
        problemas.append(
            Problema(
                secao="P",
                severidade="aviso",
                descricao="Rodapé de ciência e concordância ausente.",
                sugestao=f"Acrescente: {RODAPE_CIENCIA}.",
            )
        )
    if RODAPE_TELEMEDICINA.lower() not in plano.lower():
        problemas.append(
            Problema(
                secao="P",
                severidade="aviso",
                descricao="Rodapé de telemedicina ausente.",
                sugestao=f"Acrescente: {RODAPE_TELEMEDICINA}, não sendo possível aferição...",
            )
        )
    return problemas


def regra_campos_da_anamnese(nota: NotaSoap) -> list[Problema]:
    """MUC, AP, AF, Alergia e Hábitos fazem parte do subjetivo no template."""
    subjetivo = nota.s or ""
    if not subjetivo.strip():
        return []
    ausentes = [campo for campo in _CAMPOS_S if campo.lower() not in subjetivo.lower()]
    if not ausentes:
        return []
    return [
        Problema(
            secao="S",
            severidade="aviso",
            descricao=(
                f"Campos do subjetivo ausentes: {', '.join(c.rstrip(':') for c in ausentes)}."
            ),
            sugestao="O template preenche todos, mesmo que com negativa ('nega comorbidades').",
        )
    ]


REGRAS: tuple[Callable[[NotaSoap], list[Problema]], ...] = (
    regra_cabecalho,
    regra_secoes_obrigatorias,
    regra_cid,
    regra_plano_numerado,
    regra_sinais_alarme_no_plano,
    regra_rodape,
    regra_campos_da_anamnese,
)


def validar(nota: NotaSoap) -> list[Problema]:
    """Roda todas as regras, na ordem em que estão declaradas."""
    return [problema for regra in REGRAS for problema in regra(nota)]
