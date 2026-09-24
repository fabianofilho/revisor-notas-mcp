"""Separa a nota #TELEMEDICINA# nas seções F/S/O/A/P.

Tolerante a variação de formatação: o marcador pode vir com ou sem hífen, com
espaço sobrando, em caixa baixa. Seção ausente vira ``None`` em vez de erro, a
camada de regras é quem decide o que fazer com a falta.

Nada aqui escreve em disco ou em log: o texto é de paciente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CABECALHO = "#TELEMEDICINA#"

# -F:, - F :, f:, −F: (traço unicode). O marcador precisa abrir a linha.
_MARCADOR = re.compile(r"^[ \t]*[-–—]?[ \t]*([FSOAP])[ \t]*:[ \t]*", re.IGNORECASE | re.MULTILINE)

SECOES = ("F", "S", "O", "A", "P")


@dataclass(frozen=True)
class NotaSoap:
    """A nota separada. Cada seção é o texto entre um marcador e o próximo."""

    cabecalho_presente: bool
    f: str | None
    s: str | None
    o: str | None
    a: str | None
    p: str | None

    def secao(self, letra: str) -> str | None:
        return {"F": self.f, "S": self.s, "O": self.o, "A": self.a, "P": self.p}[letra.upper()]

    @property
    def secoes_ausentes(self) -> list[str]:
        return [letra for letra in SECOES if not (self.secao(letra) or "").strip()]


def letra_do_marcador(linha: str) -> str | None:
    """A letra da seção se a linha abre uma seção (mesmo critério do ``parse``)."""
    achado = _MARCADOR.match(linha)
    return achado.group(1).upper() if achado else None


def parse(texto: str) -> NotaSoap:
    """Separa o texto nas seções. Nunca levanta por formatação ruim."""
    bruto = texto.strip()
    cabecalho = bruto.upper().startswith(CABECALHO)

    achados = list(_MARCADOR.finditer(bruto))
    conteudo: dict[str, str] = {}
    for indice, achado in enumerate(achados):
        letra = achado.group(1).upper()
        fim = achados[indice + 1].start() if indice + 1 < len(achados) else len(bruto)
        trecho = bruto[achado.end() : fim].strip()
        # Marcador repetido: fica o primeiro, que é o que o template prevê.
        conteudo.setdefault(letra, trecho)

    return NotaSoap(
        cabecalho_presente=cabecalho,
        f=conteudo.get("F"),
        s=conteudo.get("S"),
        o=conteudo.get("O"),
        a=conteudo.get("A"),
        p=conteudo.get("P"),
    )
