from __future__ import annotations

from ast_nodes import Program, TypeName
from semantic_errors import SemanticErrorKind as K
from symbols import FunctionSymbol, Scope, Symbol, SymbolKind
from visitor import Visitor


def resolve_names(program: Program) -> None:
    """Construa escopos, símbolos e vínculos entre usos e declarações."""
    NameResolver().run(program)


class NameResolver(Visitor):
    def __init__(self):
        super().__init__()
        self.functions = {}  # tabela global, separada das variáveis
        self.scope = None

    def Program(self, node):
        # Todas as assinaturas antes dos corpos: chamadas antecipadas e recursão.
        for f in node.functions:
            symbol = FunctionSymbol(f.name, SymbolKind.FUNCTION, f.return_type,
                                    f, tuple(p.type for p in f.parameters))
            f.metadata["symbol"] = symbol
            if f.name in self.functions:
                self.error(K.DUPLICATE_FUNCTION, f, f"função '{f.name}' repetida")
            else:
                self.functions[f.name] = symbol

        main = self.functions.get("main")
        if main is None:
            self.error(K.INVALID_MAIN, node, "falta int main()")
        elif main.type != TypeName.INT or main.parameter_types:
            self.error(K.INVALID_MAIN, main.declaration, "main deve ser int main()")

        for f in node.functions:
            self.visit(f)

    def FunctionDecl(self, node):
        # Parâmetros e bloco externo do corpo dividem o mesmo escopo.
        self.scope = Scope(None)
        for p in node.parameters:
            self.declare(p, SymbolKind.PARAMETER)
        node.body.metadata["scope"] = self.scope
        for statement in node.body.statements:
            self.visit(statement)

    def Block(self, node):
        self.scope = Scope(self.scope)
        node.metadata["scope"] = self.scope
        self.children(node)
        self.scope = self.scope.parent

    def VarDecl(self, node):
        # Declara antes do inicializador: em 'int x = x;' o uso é o novo x.
        self.declare(node, SymbolKind.VARIABLE)
        self.children(node)

    def IdentifierExpr(self, node):
        scope = self.scope
        while scope and node.name not in scope.symbols:
            scope = scope.parent
        if scope:
            node.metadata["symbol"] = scope.symbols[node.name]
        else:
            self.error(K.UNDECLARED_VARIABLE, node, f"'{node.name}' não declarada")

    def CallExpr(self, node):
        if node.name in self.functions:
            node.metadata["symbol"] = self.functions[node.name]
        else:
            self.error(K.UNDECLARED_FUNCTION, node, f"'{node.name}' não existe")
        self.children(node)

    def declare(self, node, kind):
        symbol = Symbol(node.name, kind, node.type, node)
        node.metadata["symbol"] = symbol
        if node.name in self.scope.symbols:
            self.error(K.DUPLICATE_DECLARATION, node, f"'{node.name}' repetido")
        else:
            self.scope.symbols[node.name] = symbol
