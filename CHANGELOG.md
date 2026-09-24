# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). O projeto
segue [versionamento semântico](https://semver.org/lang/pt-BR/).

## [0.1.0] - 2026-09-24

Primeira versão pública. Distribuição por clone + `uv` (sem pacote no PyPI).

### O que há

- Servidor MCP (stdio) com duas tools:
  - `validar_nota_soap(texto_nota)`: lista os problemas da nota, cada um com seção,
    severidade, sugestão e origem (`regra` ou `semantica`).
  - `sugerir_correcoes(texto_nota)`: devolve a nota com anotações `<<ERRO: ...>>` e
    `<<AVISO: ...>>` inline, sem alterar nenhuma linha original.
- Regras determinísticas para o template `#TELEMEDICINA#` (F/S/O/A/P): cabeçalho, as
  cinco seções, CID-10 em formato válido, itens numerados do plano, orientação sobre
  sinais de alarme, rodapé fixo e campos do subjetivo.
- Checagem semântica opcional por LLM local (API OpenAI-compatible): coerência entre
  queixa, exame e conduta, e sinais de alarme não investigados. Se o LLM falhar, as
  regras respondem sozinhas e a resposta diz o motivo.
- Privacidade: endpoint do LLM restrito a localhost (outro host levanta
  `EndpointNaoLocal`), nada gravado em disco nem em log, fixtures 100% sintéticas.
- CLI `revisor-cli` (`validar`, `anotar`, `llm`).

### Mudou antes da tag

- `sugerir_correcoes` repetia a mesma anotação embaixo de toda linha iniciada por
  F/S/O/A/P (`AP:`, `AF:`, `Alergia:`, `Paciente ciente...`) e descartava problemas
  multissecao da camada semântica, seções em caixa baixa e seções ausentes. Agora cada
  problema aparece uma única vez, e o que não tem seção na nota vai para o bloco
  `<<PROBLEMAS NO DOCUMENTO>>`.
- `sugerir_correcoes` passa a devolver `motivo_semantica_pulada`, e o aviso das duas tools
  diz o motivo real quando a semântica não roda (antes dizia sempre que o LLM não
  respondeu). Nota vazia devolve o mesmo único erro nas duas tools.
- Os prompts do LLM foram para `src/revisor_notas_mcp/prompts/` e entram no wheel (antes a
  instalação pelo wheel perdia a checagem semântica com `TemplateNotFound`).
- Dependência corrigida para `mcp>=2.2,<3` (o código usa `mcp.server.mcpserver`, que não
  existe no SDK 1.x). O `pyproject.toml` declara a licença Apache-2.0.
- Documentação: CONTRIBUTING não fala mais em fixtures capturadas de respostas reais;
  novos SECURITY.md e CHANGELOG.md.

[0.1.0]: https://github.com/fabianofilho/revisor-notas-mcp/releases/tag/v0.1.0
