"""Tools ponta a ponta, incluindo as garantias de privacidade."""

from __future__ import annotations

import httpx
import pytest
import respx

from revisor_notas_mcp.llm.qwen_client import EndpointNaoLocal, exigir_endpoint_local
from revisor_notas_mcp.mcp_server.tools.validacao import sugerir_correcoes, validar_nota_soap
from tests.fixtures import NOTA_COMPLETA, NOTA_SEM_CID

LOCAL = "http://127.0.0.1:11434/v1"
MODELO = "modelo-de-teste"


def _chat(conteudo: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": conteudo}}]})


# --- privacidade -----------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://api.openai.com/v1",
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
