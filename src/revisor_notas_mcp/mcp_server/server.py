"""Entrypoint MCP (stdio) do revisor de notas.

Nada do texto da nota é registrado em log: o logging fica em WARNING por padrão e
nenhuma mensagem inclui conteúdo da nota.
"""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from revisor_notas_mcp.config import carregar_config
from revisor_notas_mcp.mcp_server.tools.validacao import (
    RespostaCorrecoes,
    RespostaValidacao,
)
from revisor_notas_mcp.mcp_server.tools.validacao import (
    sugerir_correcoes as _sugerir_correcoes,
)
from revisor_notas_mcp.mcp_server.tools.validacao import (
    validar_nota_soap as _validar_nota_soap,
)

logger = logging.getLogger(__name__)

mcp = MCPServer("revisor-notas-mcp", version="0.1.0")


@mcp.tool()
async def validar_nota_soap(texto_nota: str) -> RespostaValidacao:
    """Valida uma nota clínica no formato #TELEMEDICINA# (F/S/O/A/P).

    Checa campos obrigatórios, CID, numeração do plano e rodapé por regras
    determinísticas, e usa o LLM local para conferir coerência entre queixa,
    exame e conduta, além de sinais de alarme não investigados. A parte do LLM é
    probabilística e vem marcada como tal; se ele estiver fora do ar, as regras
    respondem sozinhas e motivo_semantica_pulada diz por que a semântica não rodou.

    O texto processado não sai da máquina nem é gravado em lugar nenhum.

    Args:
        texto_nota: a nota completa, como seria colada no prontuário.
    """
    config = carregar_config()
    return await _validar_nota_soap(
        texto_nota,
        qwen_endpoint=config.qwen_endpoint,
        qwen_model=config.qwen_model,
        timeout_segundos=config.timeout_checagem_semantica_segundos,
    )


@mcp.tool()
async def sugerir_correcoes(texto_nota: str) -> RespostaCorrecoes:
    """Devolve a nota com anotações inline do que precisa ser ajustado.

    Não reescreve o texto original: cada problema de validar_nota_soap vira uma
    linha <<ERRO: ...>> ou <<AVISO: ...>>, uma única vez, no fim da seção a que
    se refere. O que não tem seção na nota (cabeçalho, seção ausente) vai para
    um bloco <<PROBLEMAS NO DOCUMENTO>> no topo. Quem decide o que mudar é o
    médico.

    Args:
        texto_nota: a nota completa a ser anotada.
    """
    config = carregar_config()
    return await _sugerir_correcoes(
        texto_nota,
        qwen_endpoint=config.qwen_endpoint,
        qwen_model=config.qwen_model,
        timeout_segundos=config.timeout_checagem_semantica_segundos,
    )


def main() -> None:
    """Sobe o servidor MCP no stdio."""
    config = carregar_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger.info("revisor-notas-mcp subindo (LLM local em %s)", config.qwen_endpoint)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
