"""Parser das seções F/S/O/A/P."""

from __future__ import annotations

from revisor_notas_mcp.parser.soap import parse
from tests.fixtures import (
    NOTA_COMPLETA,
    NOTA_FORMATACAO_SOLTA,
    NOTA_SEM_CABECALHO,
    NOTA_SEM_OBJETIVO,
)


def test_separa_as_cinco_secoes() -> None:
    nota = parse(NOTA_COMPLETA)
    assert nota.secoes_ausentes == []
    assert nota.f is not None and "dor de garganta" in nota.f
    assert nota.a is not None and "J06.9" in nota.a


def test_cabecalho_detectado() -> None:
    assert parse(NOTA_COMPLETA).cabecalho_presente is True
    assert parse(NOTA_SEM_CABECALHO).cabecalho_presente is False


def test_secao_ausente_vira_none_sem_falhar() -> None:
    """Requisito: seção que falta não pode quebrar o parser."""
    nota = parse(NOTA_SEM_OBJETIVO)
    assert nota.o is None
    assert nota.secoes_ausentes == ["O"]
    assert nota.a is not None


def test_tolera_variacao_de_formatacao() -> None:
    """Marcador sem hífen, com espaço sobrando, em caixa baixa."""
    nota = parse(NOTA_FORMATACAO_SOLTA)
    assert nota.secoes_ausentes == []
    assert nota.s is not None and "tosse seca" in nota.s
    assert nota.cabecalho_presente is True


def test_texto_vazio_nao_quebra() -> None:
    nota = parse("")
    assert nota.cabecalho_presente is False
    assert nota.secoes_ausentes == ["F", "S", "O", "A", "P"]


def test_secao_nao_vaza_para_a_seguinte() -> None:
    nota = parse(NOTA_COMPLETA)
    assert nota.a is not None
    assert "Dipirona" not in nota.a
