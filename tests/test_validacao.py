"""Tools ponta a ponta, incluindo as garantias de privacidade."""

from __future__ import annotations

import httpx
import pytest
import respx

from revisor_notas_mcp.llm.checagem_semantica import _render
from revisor_notas_mcp.llm.qwen_client import EndpointNaoLocal, exigir_endpoint_local
from revisor_notas_mcp.mcp_server.tools.validacao import (
    anotar,
    sugerir_correcoes,
    validar_nota_soap,
)
from revisor_notas_mcp.rules.checklist import Problema
from tests.fixtures import (
    NOTA_COMPLETA,
    NOTA_FORMATACAO_SOLTA,
    NOTA_SEM_CABECALHO,
    NOTA_SEM_CID,
    NOTA_SEM_OBJETIVO,
)

LOCAL = "http://127.0.0.1:11434/v1"
MODELO = "modelo-de-teste"


def _chat(conteudo: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": conteudo}}]})


# --- privacidade -----------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.openai.com/v1",
        # 192.0.2.0/24 e a faixa reservada para documentacao (RFC 5737)
        "http://192.0.2.50:8080/v1",
        "http://llm.exemplo.com/v1",
    ],
)
def test_recusa_endpoint_remoto(endpoint: str) -> None:
    """Nota de paciente não vai para outro host. Nem por configuração errada."""
    with pytest.raises(EndpointNaoLocal):
        exigir_endpoint_local(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    ["http://127.0.0.1:11434/v1", "http://localhost:8080/v1", "http://[::1]:1234/v1"],
)
def test_aceita_endpoints_locais(endpoint: str) -> None:
    assert exigir_endpoint_local(endpoint) == endpoint


async def test_endpoint_remoto_nao_degrada_em_silencio() -> None:
    """Configuração perigosa tem que estourar, não virar 'semântica pulada'."""
    with pytest.raises(EndpointNaoLocal):
        await validar_nota_soap(
            NOTA_COMPLETA, qwen_endpoint="https://api.exemplo.com/v1", qwen_model=MODELO
        )


async def test_nada_da_nota_vaza_em_log(caplog: pytest.LogCaptureFixture) -> None:
    """Requisito duro: o texto da nota não aparece em log, nem quando dá erro."""
    caplog.set_level("DEBUG")
    with respx.mock:
        respx.get(f"{LOCAL}/models").mock(side_effect=httpx.ConnectError("recusado"))
        await validar_nota_soap(NOTA_COMPLETA, qwen_endpoint=LOCAL, qwen_model=MODELO)

    registrado = " ".join(r.getMessage() for r in caplog.records)
    assert "odinofagia" not in registrado
    assert "dor de garganta" not in registrado


# --- degradação ------------------------------------------------------------


@respx.mock
async def test_llm_fora_do_ar_nao_bloqueia_as_regras() -> None:
    respx.get(f"{LOCAL}/models").mock(side_effect=httpx.ConnectError("recusado"))
    resposta = await validar_nota_soap(NOTA_SEM_CID, qwen_endpoint=LOCAL, qwen_model=MODELO)

    assert resposta.checagem_semantica_feita is False
    assert resposta.motivo_semantica_pulada is not None
    assert resposta.total_erros >= 1  # o CID ausente foi pego mesmo assim


async def test_sem_llm_por_opcao() -> None:
    resposta = await validar_nota_soap(
        NOTA_SEM_CID, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    assert resposta.checagem_semantica_feita is False
    assert any("CID" in p.descricao for p in resposta.problemas)


async def test_nota_vazia() -> None:
    resposta = await validar_nota_soap("   ", qwen_endpoint=LOCAL, qwen_model=MODELO)
    assert resposta.total_erros == 1
    assert resposta.problemas[0].descricao == "Nota vazia."


# --- camada semântica ------------------------------------------------------


@respx.mock
async def test_incoerencia_vira_aviso_marcado_como_semantico() -> None:
    respx.get(f"{LOCAL}/models").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{LOCAL}/chat/completions").mock(
        side_effect=[
            _chat(
                '{"incoerencias": [{"descricao": "Conduta trata outra coisa", "secoes": ["A"]}]}'
            ),
            _chat('{"esperados": [], "mencionados": [], "ausentes": []}'),
        ]
    )
    resposta = await validar_nota_soap(NOTA_COMPLETA, qwen_endpoint=LOCAL, qwen_model=MODELO)

    assert resposta.checagem_semantica_feita is True
    semanticos = [p for p in resposta.problemas if p.origem == "semantica"]
    assert len(semanticos) == 1
    assert semanticos[0].severidade == "aviso"


@respx.mock
async def test_sinais_de_alarme_ausentes_viram_aviso() -> None:
    respx.get(f"{LOCAL}/models").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{LOCAL}/chat/completions").mock(
        side_effect=[
            _chat('{"incoerencias": []}'),
            _chat('{"esperados": ["dispneia"], "mencionados": [], "ausentes": ["estridor"]}'),
        ]
    )
    resposta = await validar_nota_soap(NOTA_COMPLETA, qwen_endpoint=LOCAL, qwen_model=MODELO)
    assert any("estridor" in p.descricao for p in resposta.problemas)


@respx.mock
async def test_resposta_do_llm_sem_json_nao_derruba() -> None:
    respx.get(f"{LOCAL}/models").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{LOCAL}/chat/completions").mock(return_value=_chat("não sei responder"))
    resposta = await validar_nota_soap(NOTA_COMPLETA, qwen_endpoint=LOCAL, qwen_model=MODELO)
    assert resposta.checagem_semantica_feita is False


# --- anotação --------------------------------------------------------------


async def test_anotacoes_preservam_o_texto_original() -> None:
    """Requisito: anotar sem reescrever."""
    resposta = await sugerir_correcoes(
        NOTA_SEM_CID, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    for linha in NOTA_SEM_CID.splitlines():
        assert linha in resposta.nota_anotada
    assert "<<ERRO:" in resposta.nota_anotada
    assert resposta.total_anotacoes >= 1


def _anotacoes(nota_anotada: str) -> list[str]:
    return [linha for linha in nota_anotada.splitlines() if linha.strip().startswith("<<")]


@pytest.mark.parametrize(
    "nota",
    [
        NOTA_SEM_CID,
        NOTA_SEM_OBJETIVO,
        NOTA_SEM_CABECALHO,
        NOTA_FORMATACAO_SOLTA,
        "",
        "texto qualquer sem soap",
    ],
)
async def test_cada_problema_aparece_exatamente_uma_vez(nota: str) -> None:
    """Regressão: a anotação se repetia em toda linha iniciada por F/S/O/A/P
    (AP:, AF:, Alergia:, Paciente ciente...) e sumia com seção ausente."""
    validacao = await validar_nota_soap(
        nota, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    resposta = await sugerir_correcoes(nota, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False)

    anotadas = [a for a in _anotacoes(resposta.nota_anotada) if a != "<<PROBLEMAS NO DOCUMENTO>>"]
    assert len(anotadas) == resposta.total_anotacoes
    assert resposta.total_anotacoes == len(validacao.problemas)
    for problema in validacao.problemas:
        assert sum(problema.descricao in a for a in anotadas) == 1, problema.descricao
    for linha in nota.splitlines():
        assert linha in resposta.nota_anotada


async def test_nota_sem_cid_anota_so_abaixo_da_avaliacao() -> None:
    resposta = await sugerir_correcoes(
        NOTA_SEM_CID, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    linhas = resposta.nota_anotada.splitlines()
    indice = next(i for i, linha in enumerate(linhas) if "Nenhum CID" in linha)
    assert linhas[indice - 1].startswith("-A:")
    assert resposta.nota_anotada.count("<<") == 1


async def test_secao_ausente_vai_para_o_bloco_do_documento() -> None:
    resposta = await sugerir_correcoes(
        NOTA_SEM_OBJETIVO, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    topo = resposta.nota_anotada.splitlines()[:2]
    assert topo[0] == "<<PROBLEMAS NO DOCUMENTO>>"
    assert "Seção -O: ausente" in topo[1]


@pytest.mark.parametrize(
    ("secao", "abaixo_de"),
    [
        ("F, A, P", "-F:"),
        ("a", "-A:"),
        ("A: Avaliação", "-A:"),
        (" P ", "-P:"),
    ],
)
def test_secao_do_llm_fora_do_padrao_e_normalizada(secao: str, abaixo_de: str) -> None:
    problema = Problema(secao=secao, severidade="aviso", descricao="incoerência sintética")
    anotada = anotar(NOTA_COMPLETA, [problema])
    assert anotada.count("incoerência sintética") == 1
    assert "PROBLEMAS NO DOCUMENTO" not in anotada
    linhas = anotada.splitlines()
    indice = next(i for i, linha in enumerate(linhas) if "incoerência sintética" in linha)
    marcadores = [
        linha for linha in linhas[:indice] if linha[:3] in {"-F:", "-S:", "-O:", "-A:", "-P:"}
    ]
    assert marcadores[-1].startswith(abaixo_de)


def test_secao_desconhecida_nao_some() -> None:
    problema = Problema(secao="X", severidade="aviso", descricao="achado sem seção")
    anotada = anotar(NOTA_COMPLETA, [problema])
    assert anotada.splitlines()[0] == "<<PROBLEMAS NO DOCUMENTO>>"
    assert anotada.count("achado sem seção") == 1


@respx.mock
async def test_incoerencia_multisecao_aparece_na_nota_anotada() -> None:
    """O achado mais importante (incoerência clínica) não pode sumir da anotação."""
    respx.get(f"{LOCAL}/models").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.post(f"{LOCAL}/chat/completions").mock(
        side_effect=[
            _chat(
                '{"incoerencias": [{"descricao": "Conduta trata outra coisa",'
                ' "secoes": ["F", "A", "P"]}]}'
            ),
            _chat('{"esperados": [], "mencionados": [], "ausentes": ["estridor"]}'),
        ]
    )
    resposta = await sugerir_correcoes(NOTA_COMPLETA, qwen_endpoint=LOCAL, qwen_model=MODELO)

    assert resposta.checagem_semantica_feita is True
    assert resposta.total_anotacoes == 2
    assert resposta.nota_anotada.count("Conduta trata outra coisa") == 1
    assert "<<AVISO [F, A, P]: Conduta trata outra coisa" in resposta.nota_anotada
    assert resposta.nota_anotada.count("estridor") == 1


# --- prompts e aviso -------------------------------------------------------


@pytest.mark.parametrize("nome", ["checar_consistencia.jinja2", "checar_sinais_alarme.jinja2"])
def test_prompts_vem_de_dentro_do_pacote(nome: str) -> None:
    """Os prompts precisam estar no pacote, senão o wheel instalado dá TemplateNotFound."""
    assert "JSON" in _render(nome)


async def test_aviso_diz_o_motivo_real() -> None:
    """Semântica desligada não pode virar 'o LLM não respondeu'."""
    resposta = await validar_nota_soap(
        NOTA_SEM_CID, qwen_endpoint=LOCAL, qwen_model=MODELO, usar_llm=False
    )
    assert resposta.aviso is not None
    assert "desligada" in resposta.aviso
    assert "não respondeu" not in resposta.aviso
