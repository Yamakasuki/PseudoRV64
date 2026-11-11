from __future__ import annotations

from dataclasses import fields

from ast_nodes import Node
from semantic_errors import SemanticDiagnostic, SemanticError


class Visitor:
    """Percorre a AST chamando o método com o nome da classe do nó."""

    def __init__(self):
        self.errors = []

    def run(self, program):
        self.visit(program)
        if self.errors:
            raise SemanticError(self.errors)

    def visit(self, node):
        return getattr(self, type(node).__name__, self.children)(node)

    def children(self, node):
        # Padrão: visita os filhos na ordem dos campos (= ordem do fonte).
        for field in fields(node):
            value = getattr(node, field.name)
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, Node):
                    self.visit(item)

    def error(self, kind, node, message):
        self.errors.append(SemanticDiagnostic(kind, message, node.span))
