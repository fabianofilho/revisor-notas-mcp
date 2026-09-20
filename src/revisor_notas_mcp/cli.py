"""CLI de administração: validar notas de exemplo fora do MCP."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from revisor_notas_mcp.config import carregar_config
from revisor_notas_mcp.llm.qwen_client import QwenClient
from revisor_notas_mcp.mcp_server.tools.validacao import sugerir_correcoes, validar_nota_soap

app = typer.Typer(help="Administração do revisor-notas-mcp", no_args_is_help=True)


def _ler_nota(caminho: Path | None) -> str:
    """Lê do arquivo ou da entrada padrão. Nada é gravado de volta."""
    if caminho is not None:
        return caminho.read_text(encoding="utf-8")
    if sys.stdin.isatty():
        typer.echo("Cole a nota e finalize com Ctrl-D:", err=True)
    return sys.stdin.read()


@app.command()
def validar(
    arquivo: Path | None = typer.Argument(default=None, help="Arquivo da nota; vazio lê do stdin"),
    sem_llm: bool = typer.Option(False, help="Só as regras determinísticas"),
) -> None:
    """Valida uma nota e imprime os problemas."""
    config = carregar_config()
    resposta = asyncio.run(
        validar_nota_soap(
            _ler_nota(arquivo),
            qwen_endpoint=config.qwen_endpoint,
            qwen_model=config.qwen_model,
            timeout_segundos=config.timeout_checagem_semantica_segundos,
            usar_llm=not sem_llm,
        )
    )
    typer.echo(f"{resposta.total_erros} erro(s), {resposta.total_avisos} aviso(s)")
    for problema in resposta.problemas:
        cor = typer.colors.RED if problema.severidade == "erro" else typer.colors.YELLOW
        typer.secho(f"  [{problema.secao}] {problema.descricao}", fg=cor)
        if problema.sugestao:
            typer.echo(f"        → {problema.sugestao}")
    if not resposta.checagem_semantica_feita:
        typer.secho(
            f"  (semântica pulada: {resposta.motivo_semantica_pulada})", fg=typer.colors.CYAN
        )


@app.command()
def anotar(
    arquivo: Path | None = typer.Argument(default=None, help="Arquivo da nota; vazio lê do stdin"),
    sem_llm: bool = typer.Option(False, help="Só as regras determinísticas"),
) -> None:
    """Imprime a nota com anotações inline."""
    config = carregar_config()
    resposta = asyncio.run(
        sugerir_correcoes(
            _ler_nota(arquivo),
            qwen_endpoint=config.qwen_endpoint,
            qwen_model=config.qwen_model,
            timeout_segundos=config.timeout_checagem_semantica_segundos,
            usar_llm=not sem_llm,
        )
    )
    typer.echo(resposta.nota_anotada)


@app.command()
def llm() -> None:
    """Verifica se o LLM local responde (e se o endpoint é mesmo local)."""
    config = carregar_config()

    async def checar() -> None:
        async with QwenClient(config.qwen_endpoint, config.qwen_model) as cliente:
            vivo = await cliente.esta_vivo()
        cor = typer.colors.GREEN if vivo else typer.colors.RED
        typer.secho(f"LLM local {'respondendo' if vivo else 'fora do ar'}", fg=cor)
        typer.echo(f"endpoint: {config.qwen_endpoint}")

    asyncio.run(checar())


if __name__ == "__main__":
    app()
