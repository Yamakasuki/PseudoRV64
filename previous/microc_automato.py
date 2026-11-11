"""Autômato determinístico do MicroC: estados, símbolos e transições.

Não conhece ``TokenKind``: se conhecesse, e ``Lexer.py`` importasse este
módulo, haveria import circular. A tradução ``Estado -> TokenKind`` mora em
``Lexer.py``. Assim o autômato só sabe estados, símbolos e para onde ir.

Cobre identificadores, inteiros, operadores e delimitadores. Strings e
comentários são rotinas manuais em ``Lexer.py``, porque cada um exige uma
posição de erro diferente da posição corrente do autômato.
"""

from __future__ import annotations

import enum


class Estado(enum.Enum):
    """Estados do autômato. ``INICIO`` é o único de partida; quais aceitam
    está em ``ESTADOS_ACEITADORES``.
    """

    INICIO = enum.auto()

    IDENT = enum.auto()
    INT = enum.auto()

    MAIS = enum.auto()
    MENOS = enum.auto()
    ASTERISCO = enum.auto()
    BARRA = enum.auto()
    PORCENTO = enum.auto()

    MENOR = enum.auto()
    MENOR_IGUAL = enum.auto()
    MAIOR = enum.auto()
    MAIOR_IGUAL = enum.auto()
    IGUAL = enum.auto()
    IGUAL_IGUAL = enum.auto()
    EXCLAMACAO = enum.auto()
    EXCLAMACAO_IGUAL = enum.auto()
    E_COMERCIAL = enum.auto()
    E_LOGICO = enum.auto()
    BARRA_VERTICAL = enum.auto()
    OU_LOGICO = enum.auto()

    ABRE_PARENTESE = enum.auto()
    FECHA_PARENTESE = enum.auto()
    ABRE_CHAVE = enum.auto()
    FECHA_CHAVE = enum.auto()
    VIRGULA = enum.auto()
    PONTO_VIRGULA = enum.auto()


#: Letras e dígitos colapsam em duas classes: identificadores e inteiros não
#: distinguem *qual* letra apareceu. Operadores continuam sendo eles mesmos,
#: porque '<' e '>' levam a estados diferentes.
LETRA = "LETRA"
DIGITO = "DIGITO"


def classificar(caractere: str) -> str:
    """Reduz um caractere ao símbolo que indexa a tabela de transições.

    O ``isascii()`` é necessário: sem ele ``"é".isalpha()`` é ``True`` e ``é``
    viraria identificador, violando a seção 3.4. Com ele ``é`` não tem transição
    e o erro léxico cai sozinho no lugar certo.
    """
    if caractere.isascii() and (caractere.isalpha() or caractere == "_"):
        return LETRA
    if caractere.isascii() and caractere.isdigit():
        return DIGITO
    return caractere


#: Tabela de transições: ``estado atual -> símbolo -> próximo estado``.
#: Estados ausentes como chave externa são finais: não sai transição deles.
TABELA_TRANSICOES: dict[Estado, dict[str, Estado]] = {
    Estado.INICIO: {
        LETRA: Estado.IDENT,
        DIGITO: Estado.INT,
        "+": Estado.MAIS,
        "-": Estado.MENOS,
        "*": Estado.ASTERISCO,
        # Só chega aqui quando não abre comentário: `_pular_ignoraveis` roda
        # antes e já descartou '//' e '/*'.
        "/": Estado.BARRA,
        "%": Estado.PORCENTO,
        "<": Estado.MENOR,
        ">": Estado.MAIOR,
        "=": Estado.IGUAL,
        "!": Estado.EXCLAMACAO,
        "&": Estado.E_COMERCIAL,
        "|": Estado.BARRA_VERTICAL,
        "(": Estado.ABRE_PARENTESE,
        ")": Estado.FECHA_PARENTESE,
        "{": Estado.ABRE_CHAVE,
        "}": Estado.FECHA_CHAVE,
        ",": Estado.VIRGULA,
        ";": Estado.PONTO_VIRGULA,
    },
    # Identificador absorve letras e dígitos; inteiro, só dígitos. É essa
    # assimetria que faz "1abc" virar INT_LITERAL(1) + IDENTIFIER(abc).
    Estado.IDENT: {LETRA: Estado.IDENT, DIGITO: Estado.IDENT},
    Estado.INT: {DIGITO: Estado.INT},
    # Operadores de dois caracteres. O munch máximo do lexer garante que estes
    # vençam seus prefixos de um caractere, sem precisar de caso especial.
    Estado.MENOR: {"=": Estado.MENOR_IGUAL},
    Estado.MAIOR: {"=": Estado.MAIOR_IGUAL},
    Estado.IGUAL: {"=": Estado.IGUAL_IGUAL},
    Estado.EXCLAMACAO: {"=": Estado.EXCLAMACAO_IGUAL},
    Estado.E_COMERCIAL: {"&": Estado.E_LOGICO},
    Estado.BARRA_VERTICAL: {"|": Estado.OU_LOGICO},
}


#: Estados que encerram um lexema válido.
#:
#: ``E_COMERCIAL``, ``BARRA_VERTICAL`` e ``INICIO`` ficam FORA de propósito: é
#: assim que "& ou | isolados são erros léxicos" (seção 3.4) vira propriedade do
#: autômato em vez de um ``if`` — a caminhada termina sem nenhum aceitador
#: visitado, que é exatamente a condição de erro.
ESTADOS_ACEITADORES: frozenset[Estado] = frozenset(
    {
        Estado.IDENT,
        Estado.INT,
        Estado.MAIS,
        Estado.MENOS,
        Estado.ASTERISCO,
        Estado.BARRA,
        Estado.PORCENTO,
        Estado.MENOR,
        Estado.MENOR_IGUAL,
        Estado.MAIOR,
        Estado.MAIOR_IGUAL,
        Estado.IGUAL,
        Estado.IGUAL_IGUAL,
        Estado.EXCLAMACAO,
        Estado.EXCLAMACAO_IGUAL,
        Estado.E_LOGICO,
        Estado.OU_LOGICO,
        Estado.ABRE_PARENTESE,
        Estado.FECHA_PARENTESE,
        Estado.ABRE_CHAVE,
        Estado.FECHA_CHAVE,
        Estado.VIRGULA,
        Estado.PONTO_VIRGULA,
    }
)


def transicao(estado: Estado, simbolo: str) -> Estado | None:
    """Devolve o estado seguinte, ou ``None`` se a caminhada trava aqui."""
    return TABELA_TRANSICOES.get(estado, {}).get(simbolo)
