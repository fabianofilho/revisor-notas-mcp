# revisor-notas-mcp

Servidor MCP que valida notas clínicas no formato SOAP `#TELEMEDICINA#` (F/S/O/A/P), o
mesmo da skill `/clude`. Roda **inteiramente local e offline**: o texto da nota nunca sai
da máquina.

## Privacidade não é um detalhe aqui

Este projeto processa texto de paciente real. Por isso:

- **Nenhuma chamada de rede além de `localhost`.** O cliente do LLM recusa, com erro, um
  endpoint que aponte para qualquer outro host — não degrada em silêncio.
- **Nada é gravado.** Sem banco, sem cache em disco, sem log do conteúdo. O processamento
  é em memória, por chamada.
- **Testes usam só notas sintéticas**, nunca dado real, nem anonimizado.

## Rodando

```bash
uv sync
cp .env.example .env
uv run revisor-cli llm                      # confirma que o LLM local responde
uv run revisor-cli validar nota.txt         # ou cole a nota no stdin
uv run revisor-cli validar nota.txt --sem-llm   # só as regras determinísticas
uv run revisor-cli anotar nota.txt          # nota com anotações inline
uv run revisor-notas-mcp                    # servidor MCP no stdio
```

## As duas camadas

**Regras determinísticas** (`rules/`) — rodam sempre, sem LLM: cabeçalho, as cinco
seções, CID em formato válido, itens 1–5 do plano, item de sinais de alarme, rodapé fixo,
e os campos do subjetivo (MUC, AP, AF, Alergia, Hábitos).

**Checagem semântica** (`llm/`) — o que regra não pega: coerência entre queixa, exame e
conduta; e sinais de alarme típicos do diagnóstico que não aparecem como investigados
(negativa explícita conta como investigado).

Se o LLM local estiver fora do ar, a validação por regras responde sozinha e a resposta
diz que a parte semântica não rodou. As regras nunca ficam bloqueadas pelo modelo.

## Tools

### `validar_nota_soap(texto_nota)`
Lista de problemas, cada um com seção, severidade (`erro`/`aviso`), descrição, sugestão e
`origem` (`regra` ou `semantica`).

### `sugerir_correcoes(texto_nota)`
A mesma nota com linhas `<<AVISO: ...>>` inseridas abaixo de cada seção. **Não reescreve
o texto original** — quem decide o que mudar é o médico.

## O que o LLM local acerta e o que não

A checagem semântica é probabilística e vem sempre marcada como tal na resposta. Ela serve
para levantar a sobrancelha, não para dar veredito: um aviso de sinal de alarme ausente
pode ser um falso positivo, e a ausência de avisos não atesta que a nota está correta.
