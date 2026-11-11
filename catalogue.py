"""Catálogo de regras normativas da Etapa 6 (pseudoRV64)."""

from ast_nodes import (
    BinaryExpr,
    BinaryOperator,
    BoolLiteral,
    CallExpr,
    IdentifierExpr,
    IntLiteral,
    TypeName,
    UnaryExpr,
    UnaryOperator,
)
from patterns import (
    COND,
    EFFECT,
    IMM12,
    POW2,
    REG,
    Args,
    Need,
    Pattern,
    Rule,
    imm12,
    neg_imm12,
    pow2,
    signed_literal,
)


def _is_bool(node) -> bool:
    t = node.metadata.get("type")
    if t is not None:
        return t == TypeName.BOOL
    sym = node.metadata.get("symbol")
    if sym is not None:
        return getattr(sym, "type", None) == TypeName.BOOL
    return False


def _is_not_void_call(node) -> bool:
    if not isinstance(node, CallExpr):
        return False
    t = node.metadata.get("type")
    if t is not None and t == TypeName.VOID:
        return False
    func = getattr(node, "function", None)
    if func is not None and getattr(func, "return_type", None) == TypeName.VOID:
        return False
    return True


def _is_bool_call(node) -> bool:
    if not isinstance(node, CallExpr):
        return False
    t = node.metadata.get("type")
    if t is not None:
        return t == TypeName.BOOL
    func = getattr(node, "function", None)
    if func is not None:
        return getattr(func, "return_type", None) == TypeName.BOOL
    return False


def catalogue():
    """Catálogo fechado de 20 famílias normativas conforme a Seção 7 do enunciado."""
    return (
        # 1. Literal inteiro com sinal ou bool para REG, com Li (Custo 1)
        Rule(
            "int_literal_reg",
            REG,
            Pattern(predicate=lambda n: signed_literal(n) is not None),
            1,
            "li_int",
        ),
        Rule("bool_literal_reg", REG, Pattern(BoolLiteral), 1, "li_bool"),
        # 2. Identificador para REG, reutilizando o VReg do símbolo (Custo 0)
        Rule("id_reg", REG, Pattern(IdentifierExpr), 0, "id_reg"),
        # 3. Literal elegível para IMM12 ou POW2, sem instrução (Custo 0)
        Rule("imm12", IMM12, Pattern(predicate=imm12), 0, "imm12"),
        Rule("pow2", POW2, Pattern(predicate=pow2), 0, "pow2"),
        # 4. Negação aritmética de REG para REG, com Neg (Custo 1)
        Rule(
            "neg_reg",
            REG,
            Pattern(UnaryExpr, UnaryOperator.NEGATE, (Need(REG),)),
            1,
            "neg",
        ),
        # 5. Aritmética geral de dois REG para REG (Custo 1)
        Rule(
            "add_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.ADD, (Need(REG), Need(REG))),
            1,
            "add",
        ),
        Rule(
            "sub_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.SUBTRACT, (Need(REG), Need(REG))),
            1,
            "sub",
        ),
        Rule(
            "mul_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.MULTIPLY, (Need(REG), Need(REG))),
            1,
            "mul",
        ),
        Rule(
            "div_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.DIVIDE, (Need(REG), Need(REG))),
            1,
            "div",
        ),
        Rule(
            "rem_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.REMAINDER, (Need(REG), Need(REG))),
            1,
            "rem",
        ),
        # 6. Soma REG/IMM12 ou IMM12/REG, com Addi (Custo 1)
        Rule(
            "add_reg_imm",
            REG,
            Pattern(BinaryExpr, BinaryOperator.ADD, (Need(REG), Need(IMM12))),
            1,
            "add_reg_imm",
        ),
        Rule(
            "add_imm_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.ADD, (Need(IMM12), Need(REG))),
            1,
            "add_imm_reg",
        ),
        # 7. Subtração REG menos literal cujo oposto cabe no imediato, com Addi (Custo 1)
        Rule(
            "sub_reg_neg_imm",
            REG,
            Pattern(
                BinaryExpr,
                BinaryOperator.SUBTRACT,
                (Need(REG), Pattern(predicate=neg_imm12)),
            ),
            1,
            "sub_reg_neg_imm",
        ),
        # 8. Multiplicação REG/POW2 ou POW2/REG, com Slli (Custo 1)
        Rule(
            "mul_reg_pow2",
            REG,
            Pattern(BinaryExpr, BinaryOperator.MULTIPLY, (Need(REG), Need(POW2))),
            1,
            "mul_reg_pow2",
        ),
        Rule(
            "mul_pow2_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.MULTIPLY, (Need(POW2), Need(REG))),
            1,
            "mul_pow2_reg",
        ),
        # 9. Menor ou maior de dois REG para REG, com Slt (Custo 1)
        Rule(
            "slt_less",
            REG,
            Pattern(BinaryExpr, BinaryOperator.LESS, (Need(REG), Need(REG))),
            1,
            "slt_less",
        ),
        Rule(
            "slt_greater",
            REG,
            Pattern(BinaryExpr, BinaryOperator.GREATER, (Need(REG), Need(REG))),
            1,
            "slt_greater",
        ),
        # 10. Menor ou igual, maior ou igual para REG, com Slt e Seqz (Custo 2)
        Rule(
            "le_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.LESS_EQUAL, (Need(REG), Need(REG))),
            2,
            "le_reg",
        ),
        Rule(
            "ge_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.GREATER_EQUAL, (Need(REG), Need(REG))),
            2,
            "ge_reg",
        ),
        # 11. Igualdade/desigualdade para REG, com Xor e Seqz/Snez (Custo 2)
        Rule(
            "eq_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.EQUAL, (Need(REG), Need(REG))),
            2,
            "eq_reg",
        ),
        Rule(
            "ne_reg",
            REG,
            Pattern(BinaryExpr, BinaryOperator.NOT_EQUAL, (Need(REG), Need(REG))),
            2,
            "ne_reg",
        ),
        # 12. Comparação de dois REG para COND, branch direto e Jump (Custo 2)
        Rule(
            "cond_less",
            COND,
            Pattern(BinaryExpr, BinaryOperator.LESS, (Need(REG), Need(REG))),
            2,
            "cond_less",
        ),
        Rule(
            "cond_greater",
            COND,
            Pattern(BinaryExpr, BinaryOperator.GREATER, (Need(REG), Need(REG))),
            2,
            "cond_greater",
        ),
        Rule(
            "cond_less_equal",
            COND,
            Pattern(BinaryExpr, BinaryOperator.LESS_EQUAL, (Need(REG), Need(REG))),
            2,
            "cond_less_equal",
        ),
        Rule(
            "cond_greater_equal",
            COND,
            Pattern(BinaryExpr, BinaryOperator.GREATER_EQUAL, (Need(REG), Need(REG))),
            2,
            "cond_greater_equal",
        ),
        Rule(
            "cond_equal",
            COND,
            Pattern(BinaryExpr, BinaryOperator.EQUAL, (Need(REG), Need(REG))),
            2,
            "cond_equal",
        ),
        Rule(
            "cond_not_equal",
            COND,
            Pattern(BinaryExpr, BinaryOperator.NOT_EQUAL, (Need(REG), Need(REG))),
            2,
            "cond_not_equal",
        ),
        # 13. Negação lógica de REG para REG, com Seqz (Custo 1)
        Rule(
            "not_reg",
            REG,
            Pattern(UnaryExpr, UnaryOperator.NOT, (Need(REG),)),
            1,
            "not_reg",
        ),
        # 14. Negação lógica de COND para COND, invertendo destinos (Custo 0)
        Rule(
            "not_cond",
            COND,
            Pattern(UnaryExpr, UnaryOperator.NOT, (Need(COND),)),
            0,
            "not_cond",
        ),
        # 15. &&/|| de dois COND para COND (Custo 0)
        Rule(
            "and_cond",
            COND,
            Pattern(
                BinaryExpr, BinaryOperator.LOGICAL_AND, (Need(COND), Need(COND))
            ),
            0,
            "and_cond",
        ),
        Rule(
            "or_cond",
            COND,
            Pattern(
                BinaryExpr, BinaryOperator.LOGICAL_OR, (Need(COND), Need(COND))
            ),
            0,
            "or_cond",
        ),
        # 16. &&/|| de dois COND para REG, com duas Li e um Jump (Custo 3)
        Rule(
            "and_reg",
            REG,
            Pattern(
                BinaryExpr, BinaryOperator.LOGICAL_AND, (Need(COND), Need(COND))
            ),
            3,
            "and_reg",
        ),
        Rule(
            "or_reg",
            REG,
            Pattern(
                BinaryExpr, BinaryOperator.LOGICAL_OR, (Need(COND), Need(COND))
            ),
            3,
            "or_reg",
        ),
        # 17. Literal bool para COND, com Jump (Custo 1)
        Rule("bool_cond", COND, Pattern(BoolLiteral), 1, "bool_cond"),
        # 18. Identificador bool para COND, com branch e Jump (Custo 2)
        Rule("id_cond", COND, Pattern(IdentifierExpr, predicate=_is_bool), 2, "id_cond"),
        # 19. Chamada com argumentos REG para REG ou EFFECT, com Call (Custo 1)
        Rule(
            "call_reg",
            REG,
            Pattern(CallExpr, children=(Args(REG),), predicate=_is_not_void_call),
            1,
            "call_reg",
        ),
        Rule(
            "call_effect",
            EFFECT,
            Pattern(CallExpr, children=(Args(REG),)),
            1,
            "call_effect",
        ),
        # 20. Chamada bool com argumentos REG para COND, com chamada e desvios (Custo 3)
        Rule(
            "call_cond",
            COND,
            Pattern(CallExpr, children=(Args(REG),), predicate=_is_bool_call),
            3,
            "call_cond",
        ),
    )
