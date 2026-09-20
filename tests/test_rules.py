"""Regras determinísticas: cada uma isolada."""

from __future__ import annotations

from revisor_notas_mcp.parser.soap import parse
from revisor_notas_mcp.rules.checklist import (
    regra_cabecalho,
    regra_campos_da_anamnese,
    regra_cid,
    regra_plano_numerado,
    regra_rodape,
    regra_secoes_obrigatorias,
    regra_sinais_alarme_no_plano,
    validar,
)
from tests.fixtures import (
    NOTA_COMPLETA,
    NOTA_SEM_ALARME,
    NOTA_SEM_CABECALHO,
    NOTA_SEM_CID,
    NOTA_SEM_OBJETIVO,
)


def test_nota_completa_passa_limpa() -> None:
    assert validar(parse(NOTA_COMPLETA)) == []


def test_cabecalho_ausente_e_erro() -> None:
    problemas = regra_cabecalho(parse(NOTA_SEM_CABECALHO))
    assert len(problemas) == 1
    assert problemas[0].severidade == "erro"


def test_secao_ausente_e_erro() -> None:
    problemas = regra_secoes_obrigatorias(parse(NOTA_SEM_OBJETIVO))
    assert [p.secao for p in problemas] == ["O"]


def test_cid_ausente_e_erro() -> None:
    problemas = regra_cid(parse(NOTA_SEM_CID))
    assert len(problemas) == 1
    assert "Nenhum CID" in problemas[0].descricao


def test_cid_em_formato_invalido_e_apontado() -> None:
    """Escreveu 'CID' mas não no formato: é diferente de ter esquecido."""
    nota = parse("#TELEMEDICINA#\n-A: Faringite (CID: dois mil).")
    problemas = regra_cid(nota)
    assert len(problemas) == 1
    assert "formato" in problemas[0].descricao


def test_cid_valido_com_subcategoria() -> None:
    assert regra_cid(parse("#TELEMEDICINA#\n-A: IVAS (CID: J06.9).")) == []
    assert regra_cid(parse("#TELEMEDICINA#\n-A: Gastroenterite (CID: A09).")) == []


def test_plano_sem_itens_e_aviso() -> None:
    problemas = regra_plano_numerado(parse(NOTA_SEM_OBJETIVO))
    assert any("itens numerados" in p.descricao for p in problemas)
    assert all(p.severidade == "aviso" for p in problemas)


def test_sinais_de_alarme_ausentes_no_plano_e_erro() -> None:
    """Orientar sobre sinais de alarme é o item que mais importa clinicamente."""
    problemas = regra_sinais_alarme_no_plano(parse(NOTA_SEM_ALARME))
    assert len(problemas) == 1
    assert problemas[0].severidade == "erro"


def test_rodape_ausente_e_aviso() -> None:
    nota = parse(
        NOTA_COMPLETA.replace("Paciente ciente e concordante com plano terapêutico.\n", "")
    )
    problemas = regra_rodape(nota)
    assert any("ciência" in p.descricao for p in problemas)


def test_campos_do_subjetivo_ausentes() -> None:
    nota = parse(NOTA_COMPLETA.replace("Alergia: nega alergia medicamentosa conhecida.\n", ""))
    problemas = regra_campos_da_anamnese(nota)
    assert len(problemas) == 1
    assert "Alergia" in problemas[0].descricao


def test_regras_nao_falham_com_nota_vazia() -> None:
    """A validação precisa responder mesmo com lixo na entrada."""
    problemas = validar(parse(""))
    assert any(p.severidade == "erro" for p in problemas)
