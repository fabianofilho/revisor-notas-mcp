# revisor-notas-mcp

Servidor MCP que confere notas clínicas no formato SOAP (F/S/O/A/P): checa se os campos
obrigatórios estão preenchidos e usa um LLM local para apontar incoerências entre queixa,
exame e conduta. Roda inteiramente na sua máquina — o texto da nota não sai dela.

> ### ⚠️ Não substitui o julgamento clínico
>
> - **Isto não é um software de apoio à decisão clínica.** Não foi validado clinicamente,
>   não foi avaliado por nenhum órgão regulador e não é um dispositivo médico.
> - **A checagem semântica é probabilística.** Ela é feita por um LLM lendo texto livre:
>   erra para os dois lados. Ausência de avisos não atesta que a nota está correta, e um
>   aviso pode ser falso positivo.
> - **A responsabilidade pela nota continua sendo de quem assina.** A ferramenta aponta o
>   que pode ter faltado; ela não sabe do paciente nada além do que está escrito.
> - O projeto foi escrito em torno de um template específico de telemedicina. Se o seu
>   formato for outro, as regras determinísticas precisam ser ajustadas.

## Requisitos

| O quê | Versão | Para quê |
| --- | --- | --- |
| Python | 3.12+ | runtime |
| [uv](https://docs.astral.sh/uv/) | recente | dependências e venv |
| Um LLM local com API OpenAI-compatible | — | checagem semântica (opcional) |

Sem banco de dados: este projeto não persiste nada.

## Instalação

```bash
git clone https://github.com/fabianofilho/revisor-notas-mcp.git
cd revisor-notas-mcp
uv sync
cp .env.example .env
```

## Configuração

| Variável | Padrão | Observação |
| --- | --- | --- |
| `QWEN_ENDPOINT` | `http://127.0.0.1:8080/v1` | llama.cpp. Ollama: `:11434/v1`. LM Studio: `:1234/v1` |
| `QWEN_MODEL` | `local-model` | llama.cpp e LM Studio aceitam qualquer nome |
| `TIMEOUT_CHECAGEM_SEMANTICA_SEGUNDOS` | `15` | curto de propósito: a checagem não pode travar a resposta |

**O endpoint precisa ser localhost.** Qualquer outro host é recusado com exceção, não com
aviso — ver [Privacidade](#privacidade).

```bash
uv run revisor-cli llm                        # confirma o LLM local
uv run revisor-cli validar nota.txt           # ou cole a nota no stdin
uv run revisor-cli validar nota.txt --sem-llm # só as regras determinísticas
uv run revisor-cli anotar nota.txt            # nota com anotações inline
```

### Ligando ao Claude Code

```bash
claude mcp add revisor-notas --scope user \
  -e QWEN_ENDPOINT=http://127.0.0.1:8080/v1 \
  -e QWEN_MODEL=local-model \
  -- uv --directory /caminho/para/revisor-notas-mcp run revisor-notas-mcp
```

## Uso

### `validar_nota_soap(texto_nota: str)`

Lista os problemas encontrados, cada um com seção, severidade, sugestão e a `origem`
(`regra` ou `semantica`).

```json
{
  "total_erros": 0,
  "total_avisos": 2,
  "checagem_semantica_feita": true,
  "problemas": [
    {
      "secao": "F, S, A, P",
      "severidade": "aviso",
      "descricao": "A queixa é dor torácica irradiando para o braço esquerdo, com hipertensão e tabagismo, o que sugere etiologia cardíaca. A hipótese final é dor muscular e a conduta é analgésico simples.",
      "origem": "semantica"
    },
    {
      "secao": "S",
      "severidade": "aviso",
      "descricao": "Sinais de alarme esperados que não aparecem como investigados: sudorese, dispneia, náuseas.",
      "origem": "semantica"
    }
  ]
}
```

Esse exemplo é a saída real de uma nota sintética de teste. Note que `total_erros` é zero:
a nota está **formalmente correta** — as regras determinísticas passam limpo. O que a
camada semântica aponta é clínico, e é exatamente o que regra não pega.

### `sugerir_correcoes(texto_nota: str)`

A mesma nota com linhas `<<AVISO: ...>>` inseridas abaixo de cada seção. **Não reescreve o
texto original**: quem decide o que mudar é quem assina.

## As duas camadas

**Regras determinísticas** (`rules/`) — rodam sempre, sem LLM: cabeçalho, as cinco seções,
CID em formato válido, itens numerados do plano, item de sinais de alarme, rodapé fixo, e
os campos do subjetivo (medicações em uso, antecedentes, alergia, hábitos).

**Checagem semântica** (`llm/`) — coerência entre queixa, exame e conduta; e sinais de
alarme típicos do diagnóstico que não aparecem como investigados (negativa explícita conta
como investigado).

Se o LLM local estiver fora do ar, a validação por regras responde sozinha e a resposta
diz que a parte semântica não rodou. As regras nunca ficam bloqueadas pelo modelo.

## Limitações conhecidas

**O parser espera um template específico.** Ele tolera variação de formatação (marcador
com ou sem hífen, caixa baixa, espaço sobrando), mas as regras de conteúdo — quais campos
são obrigatórios, qual rodapé, quais itens no plano — foram escritas para um template de
telemedicina. Adaptar para outro formato significa mexer em `rules/checklist.py`.

**A checagem semântica depende de um modelo pequeno.** Rodando local, ela custa alguns
segundos e a qualidade varia com o modelo. Um modelo fraco vai gerar falso positivo.

**A validação de CID é sintática, não semântica.** Ela confere o formato (letra + dois
dígitos, com subcategoria opcional), não se o código corresponde ao diagnóstico escrito.

**Nada é cacheado.** Cada chamada reprocessa a nota do zero, porque cachear significaria
guardar o texto — e isso o projeto não faz.

## Privacidade

Este é o ponto central do projeto, e ele está em código e em teste, não só aqui:

- **Nenhuma chamada de rede além de `localhost`.** O cliente do LLM **recusa com exceção**
  (`EndpointNaoLocal`) um endpoint que aponte para qualquer outro host. Configuração
  perigosa estoura em vez de degradar em silêncio.
- **Nada é gravado.** Sem banco, sem cache em disco, sem log do conteúdo. O processamento
  é em memória, por chamada. Há um teste que confere que nenhum trecho da nota aparece em
  log, inclusive quando a chamada ao LLM falha.
- **Fixtures de teste são sintéticas**, nunca dado real, nem anonimizado.
- Sem telemetria, sem analytics.

O que sai da sua máquina: nada. O que vai para o seu LLM local: o texto da nota, pelo
`localhost`.

## Contribuindo

Veja [CONTRIBUTING.md](CONTRIBUTING.md). A regra mais importante e sem exceção: **nenhuma
fixture pode conter dado real de paciente**, nem anonimizado.

## Licença e atribuição

[Apache License 2.0](LICENSE) — escolhida por o projeto tocar em dado de paciente, onde a
cláusula explícita de patente é mais protetiva.

Construído no contexto do [IA.med](https://iamed.cc).
