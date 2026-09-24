# Segurança

## Como reportar

Não publique detalhes de uma vulnerabilidade em issue aberta. Abra uma
[issue](https://github.com/fabianofilho/revisor-notas-mcp/issues/new) só com o título
`Contato de seguranca`, sem descrever o problema, e o mantenedor combina um canal privado
para receber os detalhes.

No canal privado, inclua a versão (ou o commit), os passos para reproduzir e o impacto esperado. **Nunca
envie nota clínica real**, nem anonimizada: monte o exemplo com texto sintético.

Este é um projeto mantido por uma pessoa só. A resposta é por melhor esforço, sem prazo
garantido.

## Escopo

Conta como vulnerabilidade, entre outros:

- qualquer caminho em que o texto da nota saia da máquina (endpoint não local aceito,
  chamada de rede além de localhost);
- texto da nota gravado em disco, em cache ou em log;
- dependência com vulnerabilidade conhecida que seja alcançável pelo código.

Fora do escopo:

- qualidade clínica das sugestões do LLM (falso positivo ou falso negativo): é limitação
  documentada, não falha de segurança;
- a segurança do próprio LLM local e do cliente MCP, que são de terceiros.

## Versões suportadas

Só a versão mais recente (hoje, 0.1.0) recebe correção.
