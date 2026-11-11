from __future__ import annotations

from ast_nodes import Program, StringLiteral, TypeName, UnaryOperator
from semantic_errors import SemanticErrorKind as K
from visitor import Visitor

INT, BOOL, VOID = TypeName.INT, TypeName.BOOL, TypeName.VOID
MAX_INT = 2**63 - 1

# None é o "tipo desconhecido": resulta de um erro já reportado e impede
# erros em cascata. Não é um TypeName e nunca vai para metadata.


def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""
    TypeChecker().run(program)


class TypeChecker(Visitor):
    def visit(self, node):
        result = super().visit(node)
        if result is not None:  # só expressões devolvem tipo
            node.metadata["type"] = result
        return result

    # ---------- declarações e comandos

    def FunctionDecl(self, node):
        for p in node.parameters:
            if p.type == VOID:
                self.error(K.VOID_PARAMETER, p, "parâmetro void")
        self.function = node
        self.visit(node.body)

    def VarDecl(self, node):
        if node.type == VOID:
            self.error(K.VOID_VARIABLE, node, "variável void")
            if node.initializer:
                self.visit(node.initializer)
        elif node.initializer:
            self.expect(node.initializer, node.type, K.INITIALIZER_TYPE_MISMATCH)

    def Assignment(self, node):
        self.expect(node.value, self.visit(node.target), K.ASSIGNMENT_TYPE_MISMATCH)

    def IfStmt(self, node):
        self.expect(node.condition, BOOL, K.CONDITION_TYPE_MISMATCH)
        self.visit(node.then_block)
        if node.else_block:
            self.visit(node.else_block)

    def WhileStmt(self, node):
        self.expect(node.condition, BOOL, K.CONDITION_TYPE_MISMATCH)
        self.visit(node.body)

    def ReturnStmt(self, node):
        expected = self.function.return_type
        if node.value is None:
            if expected != VOID:
                self.error(K.RETURN_MISMATCH, node, "return sem valor")
        elif expected == VOID:
            self.visit(node.value)
            self.error(K.RETURN_MISMATCH, node.value, "função void com valor")
        else:
            self.expect(node.value, expected, K.RETURN_MISMATCH)

    def PrintStmt(self, node):
        for item in node.items:
            if not isinstance(item, StringLiteral):
                self.value(item)

    # ---------- expressões (devolvem o tipo)

    def IntLiteral(self, node):
        if node.value > MAX_INT:
            self.error(K.INTEGER_LITERAL_OUT_OF_RANGE, node, "literal grande demais")
        return INT

    def BoolLiteral(self, node):
        return BOOL

    def IdentifierExpr(self, node):
        type_ = node.metadata["symbol"].type
        return None if type_ == VOID else type_  # void já foi reportado

    def UnaryExpr(self, node):
        operand = self.value(node.operand)
        expected = INT if node.operator == UnaryOperator.NEGATE else BOOL
        if operand is None:
            return None
        if operand != expected:
            self.error(K.INVALID_UNARY_OPERAND, node, "operando inválido")
            return None
        return expected

    def BinaryExpr(self, node):
        left = self.value(node.left)
        right = self.value(node.right)
        if left is None or right is None:
            return None
        op = node.operator.value
        if op in ("+", "-", "*", "/", "%"):
            ok, result = left == right == INT, INT
        elif op in ("<", "<=", ">", ">="):
            ok, result = left == right == INT, BOOL
        elif op in ("==", "!="):
            ok, result = left == right, BOOL
        else:  # && ||
            ok, result = left == right == BOOL, BOOL
        if not ok:
            self.error(K.INVALID_BINARY_OPERANDS, node, "operandos inválidos")
            return None
        return result

    def CallExpr(self, node):
        function = node.metadata["symbol"]
        params = function.parameter_types
        if len(node.arguments) != len(params):
            self.error(K.ARITY_MISMATCH, node, "número de argumentos errado")
        types = [self.value(arg) for arg in node.arguments]  # visita todos
        for arg, type_, param in zip(node.arguments, types, params):
            if type_ and param != VOID and type_ != param:
                self.error(K.ARGUMENT_TYPE_MISMATCH, arg, "argumento com tipo errado")
        return function.type

    # ---------- apoio

    def value(self, node):
        """Tipo de uma expressão usada como valor: chamada void não vale."""
        type_ = self.visit(node)
        if type_ == VOID:
            self.error(K.VOID_VALUE_USED, node, "chamada void usada como valor")
            return None
        return type_

    def expect(self, node, expected, kind):
        type_ = self.value(node)
        if type_ and expected and type_ != expected:
            self.error(kind, node, f"esperado {expected.value}, veio {type_.value}")
