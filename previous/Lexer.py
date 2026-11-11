"""Analisador léxico do MicroC — Etapa 1 do projeto de Compiladores.

Estratégia **mista**, como permite a seção 5 do enunciado: um **autômato
dirigido por tabela** (``microc_automato``) reconhece identificadores,
inteiros, operadores e delimitadores pela regra do maior prefixo; **rotinas
manuais** neste arquivo cuidam de espaços, comentários e strings.

A divisão não é arbitrária: erro de string ou de comentário é reportado numa
posição que **não** é a corrente — a aspa de abertura, a barra invertida, o
``/`` inicial. O autômato só sabe onde está agora.

Racional completo em ``docs/superpowers/specs/2026-08-20-lexer-microc-design.md``,
no repositório da Etapa 1 (``Lexer``), não neste.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterator

from microc_automato import (
    ESTADOS_ACEITADORES,
    Estado,
    classificar,
    transicao,
)
from microc_cursor import Cursor


class TokenKind(enum.Enum):
    """Classe já implementada: nomes e números não devem ser alterados."""

    EOF = -1

    IDENTIFIER = 1
    INT_LITERAL = 2
    STRING_LITERAL = 3

    KW_INT = 10
    KW_BOOL = 11
    KW_VOID = 12
    KW_TRUE = 13
    KW_FALSE = 14
    KW_IF = 15
    KW_ELSE = 16
    KW_WHILE = 17
    KW_RETURN = 18
    KW_PRINT = 19

    PLUS = 20
    MINUS = 21
    STAR = 22
    SLASH = 23
    PERCENT = 24
    LESS = 25
    LESS_EQUAL = 26
    GREATER = 27
    GREATER_EQUAL = 28
    EQUAL_EQUAL = 29
    NOT_EQUAL = 30
    LOGICAL_AND = 31
    LOGICAL_OR = 32
    LOGICAL_NOT = 33
    ASSIGN = 34

    LEFT_PAREN = 40
    RIGHT_PAREN = 41
    LEFT_BRACE = 42
    RIGHT_BRACE = 43
    COMMA = 44
    SEMICOLON = 45


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    value: int | str | bool | None
    line: int
    column: int

    def __str__(self) -> str:
        return (
            f"<{self.kind.value}, {self.kind.name}, {self.lexeme!r}, "
            f"{self.value!r}, {self.line}, {self.column}>"
            # formato <numero, NOME, lexeme, value, linha, coluna> do §6
        )


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"erro léxico em {self.line}:{self.column}: {self.message}"


#: Palavras reservadas do MicroC.
#:
#: A consulta acontece **depois** de o autômato consumir o identificador
#: inteiro (seção 3.1). É isso que faz ``intx``, ``true1`` e ``_int`` serem
#: ``IDENTIFIER``, e ``While`` não casar com ``while``.
PALAVRAS_RESERVADAS: dict[str, TokenKind] = {
    "int": TokenKind.KW_INT,
    "bool": TokenKind.KW_BOOL,
    "void": TokenKind.KW_VOID,
    "true": TokenKind.KW_TRUE,
    "false": TokenKind.KW_FALSE,
    "if": TokenKind.KW_IF,
    "else": TokenKind.KW_ELSE,
    "while": TokenKind.KW_WHILE,
    "return": TokenKind.KW_RETURN,
    "print": TokenKind.KW_PRINT,
}


#: Tradução do estado final do autômato para o tipo público do token. Mora aqui,
#: e não em ``microc_automato``, para aquele módulo não importar ``TokenKind``.
ESTADO_PARA_TIPO: dict[Estado, TokenKind] = {
    Estado.IDENT: TokenKind.IDENTIFIER,
    Estado.INT: TokenKind.INT_LITERAL,
    Estado.MAIS: TokenKind.PLUS,
    Estado.MENOS: TokenKind.MINUS,
    Estado.ASTERISCO: TokenKind.STAR,
    Estado.BARRA: TokenKind.SLASH,
    Estado.PORCENTO: TokenKind.PERCENT,
    Estado.MENOR: TokenKind.LESS,
    Estado.MENOR_IGUAL: TokenKind.LESS_EQUAL,
    Estado.MAIOR: TokenKind.GREATER,
    Estado.MAIOR_IGUAL: TokenKind.GREATER_EQUAL,
    Estado.IGUAL: TokenKind.ASSIGN,
    Estado.IGUAL_IGUAL: TokenKind.EQUAL_EQUAL,
    Estado.EXCLAMACAO: TokenKind.LOGICAL_NOT,
    Estado.EXCLAMACAO_IGUAL: TokenKind.NOT_EQUAL,
    Estado.E_LOGICO: TokenKind.LOGICAL_AND,
    Estado.OU_LOGICO: TokenKind.LOGICAL_OR,
    Estado.ABRE_PARENTESE: TokenKind.LEFT_PAREN,
    Estado.FECHA_PARENTESE: TokenKind.RIGHT_PAREN,
    Estado.ABRE_CHAVE: TokenKind.LEFT_BRACE,
    Estado.FECHA_CHAVE: TokenKind.RIGHT_BRACE,
    Estado.VIRGULA: TokenKind.COMMA,
    Estado.PONTO_VIRGULA: TokenKind.SEMICOLON,
}


#: Caracteres descartados entre tokens: os três que a seção 3.2 nomeia. ``\r``
#: fica FORA de propósito — o runner lê em modo texto e já normalizou ``\r\n``
#: (seção 2.3), então um ``\r`` avulso é erro léxico pela seção 3.4, em vez de
#: ser tolerado em silêncio.
ESPACOS = " \t\n"


#: As quatro sequências de escape reconhecidas dentro de string (seção 3.3).
#: Qualquer outra é erro léxico, reportado na posição da barra invertida.
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


class Lexer:
    """Converte texto-fonte MicroC em uma sequência de tokens."""

    def __init__(self, source: str):
        self.source = source
        self._cursor = Cursor(source)

    def tokens(self) -> Iterator[Token]:
        """Produz todos os tokens significativos e um único EOF ao final.

        O cursor é recriado a cada chamada, para que percorrer o mesmo
        ``Lexer`` duas vezes devolva o mesmo resultado.
        """
        self._cursor = Cursor(self.source)

        while True:
            # Roda ANTES do teste de fim: assim o EOF sai na posição correta
            # (entrada vazia -> 1:1; texto terminado em '\n' -> linha seguinte).
            self._pular_ignoraveis()

            if self._cursor.fim():
                linha, coluna = self._cursor.posicao()
                yield Token(TokenKind.EOF, "", None, linha, coluna)
                return  # garante EOF único em todos os caminhos

            if self._cursor.espiar() == '"':
                yield self._ler_string()
            else:
                yield self._rodar_automato()

    def scan(self) -> list[Token]:
        return list(self.tokens())
        # Se algo levantar LexerError no meio, o list() propaga sem devolver
        # nada: erro nunca deixa lista parcial vazar para quem chamou (item 6).

    # ------------------------------------------------------------------
    # Núcleo dirigido por tabela
    # ------------------------------------------------------------------

    def _rodar_automato(self) -> Token:
        """Reconhece o maior prefixo válido a partir da posição corrente.

        Sem backtracking: em vez de consumir e retroceder quando trava, olha
        adiante com ``espiar(n)`` sem consumir, memoriza o último estado
        aceitador visitado e só no fim consome o tanto que foi aceito.

        Três exigências do enunciado caem daqui sem caso especial:

        * ``<=`` vence ``<`` — a caminhada vai mais longe e ``tamanho_aceito``
          é sobrescrito (idem ``>=``, ``==``, ``!=``, ``&&``, ``||``);
        * ``1abc`` vira dois tokens — o ``a`` não tem transição saindo de
          ``INT``, e consumimos só o que foi aceito;
        * ``&`` isolado é erro na coluna certa — ``E_COMERCIAL`` não aceita,
          então ``ultimo_aceitador`` continua ``None``.
        """
        linha, coluna = self._cursor.posicao()  # início do lexema, para o erro

        estado = Estado.INICIO
        adiante = 0
        ultimo_aceitador: Estado | None = None
        tamanho_aceito = 0

        while True:
            caractere = self._cursor.espiar(adiante)
            if caractere == "":
                break  # fim do texto: string vazia não casa com nada

            proximo = transicao(estado, classificar(caractere))
            if proximo is None:
                break  # a caminhada travou

            estado = proximo
            adiante += 1
            if estado in ESTADOS_ACEITADORES:
                ultimo_aceitador = estado
                tamanho_aceito = adiante  # memoriza o maior prefixo válido

        if ultimo_aceitador is None:
            raise LexerError(self._descrever_caractere_invalido(), linha, coluna)

        lexema = "".join(self._cursor.avancar() for _ in range(tamanho_aceito))
        return self._montar_token(ultimo_aceitador, lexema, linha, coluna)

    def _montar_token(self, estado: Estado, lexema: str, linha: int, coluna: int) -> Token:
        """Traduz estado final + lexema no ``Token`` público."""
        tipo = ESTADO_PARA_TIPO[estado]

        # A tabela de palavras reservadas só é consultada depois de o
        # identificador inteiro ter sido consumido.
        if tipo is TokenKind.IDENTIFIER:
            tipo = PALAVRAS_RESERVADAS.get(lexema, TokenKind.IDENTIFIER)

        valor: int | str | bool | None
        if tipo is TokenKind.IDENTIFIER:
            valor = lexema
        elif tipo is TokenKind.INT_LITERAL:
            # "0042" -> 42: os zeros sobrevivem só no lexema (seção 2.2). Limite
            # de magnitude não é desta etapa — validar 2**63-1 cabe à semântica.
            valor = int(lexema)
        elif tipo is TokenKind.KW_TRUE:
            valor = True
        elif tipo is TokenKind.KW_FALSE:
            valor = False
        else:
            valor = None

        return Token(tipo, lexema, valor, linha, coluna)
    def _descrever_caractere_invalido(self) -> str:
        """Mensagem do erro léxico para o caractere na posição corrente."""
        caractere = self._cursor.espiar()
        if not caractere.isascii():
            return f"caractere não ASCII {caractere!r} (o fonte MicroC é ASCII)"
        if caractere == "&":
            return "'&' isolado; o operador lógico do MicroC é '&&'"
        if caractere == "|":
            return "'|' isolado; o operador lógico do MicroC é '||'"
        return f"caractere inesperado {caractere!r}"

    # ------------------------------------------------------------------
    # Rotinas manuais: espaços e comentários
    # ------------------------------------------------------------------

    def _pular_ignoraveis(self) -> None:
        """Descarta espaços e comentários até o próximo token significativo.

        Um laço só, porque as três coisas se alternam livremente. Nada aqui
        produz token: não há ``TokenKind`` para espaço nem para comentário.
        """
        while not self._cursor.fim():
            caractere = self._cursor.espiar()

            if caractere in ESPACOS:
                self._cursor.avancar()
            elif caractere == "/" and self._cursor.espiar(1) == "/":
                self._pular_comentario_de_linha()
            elif caractere == "/" and self._cursor.espiar(1) == "*":
                self._pular_comentario_de_bloco()
            else:
                return  # começa um token de verdade

    def _pular_comentario_de_linha(self) -> None:
        """Consome ``//`` até a quebra de linha, sem consumi-la.

        Deixar o ``\\n`` para o laço externo concentra a contagem de linha num
        lugar só. O comentário também pode terminar no fim do arquivo.
        """
        self._cursor.avancar()  # primeira '/'
        self._cursor.avancar()  # segunda '/'

        while not self._cursor.fim() and self._cursor.espiar() != "\n":
            self._exigir_ascii()
            self._cursor.avancar()

    def _pular_comentario_de_bloco(self) -> None:
        """Consome ``/* ... */``, terminando no primeiro ``*/``.

        Blocos **não aninham** (seção 3.2), então não contamos níveis: ``/*/``
        não fecha, porque depois do ``/*`` sobra só ``/``.
        """
        # Capturado antes de consumir qualquer coisa: se o bloco não fechar, o
        # erro tem de apontar o '/' inicial, não o fim do arquivo.
        linha, coluna = self._cursor.posicao()

        self._cursor.avancar()  # '/'
        self._cursor.avancar()  # '*'

        while True:
            if self._cursor.fim():
                raise LexerError("comentário de bloco não terminado", linha, coluna)

            if self._cursor.espiar() == "*" and self._cursor.espiar(1) == "/":
                self._cursor.avancar()
                self._cursor.avancar()
                return

            self._exigir_ascii()
            self._cursor.avancar()

    def _exigir_ascii(self) -> None:
        """Rejeita caractere não ASCII na posição corrente.

        Chamado de dentro dos comentários porque a seção 3.2 é explícita: não
        ASCII é inválido mesmo dentro de comentário. Fora deles quem cuida é o
        autômato, via ``classificar``.
        """
        caractere = self._cursor.espiar()
        if not caractere.isascii():
            linha, coluna = self._cursor.posicao()
            raise LexerError(
                f"caractere não ASCII {caractere!r} (o fonte MicroC é ASCII)",
                linha,
                coluna,
            )

    # ------------------------------------------------------------------
    # Rotina manual: strings
    # ------------------------------------------------------------------

    def _ler_string(self) -> Token:
        """Reconhece um literal de string, acumulando lexema e valor em paralelo.

        O ``lexeme`` preserva a grafia original; o ``value`` guarda o conteúdo
        decodificado, sem aspas (seção 3.3) — por isso as duas listas crescem
        lado a lado.

        As três posições de erro distintas são o motivo de esta rotina não
        estar no autômato:

        * EOF antes de fechar -> a **aspa de abertura**;
        * quebra de linha -> a **própria quebra**;
        * escape inválido -> a **barra invertida**.
        """
        linha, coluna = self._cursor.posicao()  # a aspa de abertura

        partes_lexema = [self._cursor.avancar()]  # consome a aspa
        partes_valor: list[str] = []

        while True:
            if self._cursor.fim():
                raise LexerError("string não terminada", linha, coluna)

            caractere = self._cursor.espiar()

            if caractere == "\n":
                quebra_linha, quebra_coluna = self._cursor.posicao()
                raise LexerError(
                    "quebra de linha dentro de string", quebra_linha, quebra_coluna
                )

            self._exigir_ascii()

            if caractere == '"':
                partes_lexema.append(self._cursor.avancar())
                break

            if caractere == "\\":
                barra_linha, barra_coluna = self._cursor.posicao()
                partes_lexema.append(self._cursor.avancar())  # a barra

                if self._cursor.fim():
                    raise LexerError("string não terminada", linha, coluna)

                grafia = self._cursor.espiar()
                if grafia not in ESCAPES:
                    raise LexerError(
                        f"sequência de escape inválida '\\{grafia}'",
                        barra_linha,
                        barra_coluna,
                    )

                partes_lexema.append(self._cursor.avancar())
                partes_valor.append(ESCAPES[grafia])
                continue

            # Marcadores de comentário aqui dentro são só conteúdo: nada de
            # `_pular_ignoraveis` roda no meio de uma string.
            partes_lexema.append(self._cursor.avancar())
            partes_valor.append(caractere)

        return Token(
            TokenKind.STRING_LITERAL,
            "".join(partes_lexema),
            "".join(partes_valor),
            linha,
            coluna,
        )

