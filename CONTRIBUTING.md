# Contribuindo

Obrigado pelo interesse. Este e um projeto pequeno, mantido por uma pessoa so, entao
issues e PRs objetivos sao os mais faceis de tratar.

## Rodando localmente

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12+.

```bash
uv sync
cp .env.example .env     # ajuste o endpoint do seu LLM local
uv run pytest -q         # testes
uv run ruff check .      # lint
uv run ruff format .     # formatacao
uv run mypy              # tipos
```

Os testes rodam **offline**: as respostas das APIs externas estao mockadas com `respx`, e
as fixtures foram capturadas de respostas reais. Nao e preciso rede nem LLM para testar.

## Padrao de commit

Assunto no imperativo, em uma linha curta, seguido de um corpo explicando **por que** a
mudanca e necessaria. Se a mudanca veio de um comportamento observado (um parser que
quebrou, uma API que respondeu diferente), descreva o caso concreto.

Antes de abrir o PR, rode os quatro comandos acima. O CI roda os mesmos.

## Nenhuma fixture pode conter dado real de paciente

Esta e a regra mais importante deste repositorio, e nao tem excecao.

- Fixtures de teste usam **exclusivamente** notas sinteticas, inventadas para o teste.
- Nao vale usar dado real anonimizado. Anonimizacao falha, e o risco nao compensa.
- Se um PR incluir qualquer texto que pareca uma nota clinica de atendimento real, ele
  sera recusado sem revisao do resto.

Pelo mesmo motivo, nao aceite mudancas que facam o projeto gravar a nota em disco,
manda-la para um endpoint remoto ou registra-la em log.
