"""Navegação sobre o texto-fonte, com rastreamento de linha e coluna.

Não sabe nada sobre MicroC: só anda por uma string e informa onde está.

Posição conforme a seção 2.3 do enunciado: linha e coluna começam em 1;
consumir ``\\n`` incrementa a linha e zera a coluna; qualquer outro caractere
— inclusive tabulação — incrementa a coluna em 1.
"""

from __future__ import annotations


class Cursor:
    """Aponta para uma posição do texto-fonte e sabe avançar sobre ela.

        cursor = Cursor("int x")
        cursor.espiar()      # 'i', sem consumir
        cursor.avancar()     # 'i', consumindo
        cursor.posicao()     # (1, 2)

    Não existe ``voltar()``: o maior prefixo é achado com ``espiar(n)``, sem
    consumir, e só depois se consome o que foi aceito — então o cursor nunca
    precisa desfazer contagem de linha ou coluna.
    """

    def __init__(self, texto: str) -> None:
        self._texto = texto
        self._indice = 0
        self._linha = 1
        self._coluna = 1

    @property
    def linha(self) -> int:
        return self._linha

    @property
    def coluna(self) -> int:
        return self._coluna

    def posicao(self) -> tuple[int, int]:
        """Devolve ``(linha, coluna)`` do caractere ainda não consumido."""
        return self._linha, self._coluna

    def fim(self) -> bool:
        """Informa se todo o texto já foi consumido."""
        return self._indice >= len(self._texto)

    def espiar(self, adiante: int = 0) -> str:
        """Devolve o caractere ``adiante`` posições à frente, sem consumir.

        Fora do texto devolve string vazia, que não casa com nenhum símbolo da
        tabela de transições: o fim do texto se comporta como "caractere sem
        transição", sem precisar de teste separado.
        """
        indice = self._indice + adiante
        if indice >= len(self._texto):
            return ""
        return self._texto[indice]

    def avancar(self) -> str:
        """Consome um caractere, atualiza linha/coluna e o devolve.

        Com o texto esgotado levanta ``IndexError``: quem chama testa ``fim()``
        antes.
        """
        caractere = self._texto[self._indice]
        self._indice += 1
        if caractere == "\n":
            self._linha += 1
            self._coluna = 1
        else:
            self._coluna += 1
        return caractere
