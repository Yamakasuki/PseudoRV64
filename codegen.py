"""Geração de código pseudoRV64 e seleção de instruções com DP."""

from __future__ import annotations

import load_previous
from ast_nodes import (
    Assignment,
    Block,
    CallStmt,
    FunctionDecl,
    IfStmt,
    PrintStmt,
    ReturnStmt,
    StringLiteral,
    TypeName,
    VarDecl,
    WhileStmt,
)
from catalogue import catalogue
import ir as I
from ir import Context, FunctionIR, ProgramIR
from patterns import COND, EFFECT, REG, signed_literal
from selector import Selector


class CodeGenerator:
    """Coordene comandos ad hoc e seleção de expressões com DP."""

    def __init__(self):
        self.rules = catalogue()
        self.selector = Selector(self.rules)
        self.program_ir: ProgramIR | None = None
        self.function_ir: FunctionIR | None = None
        self.context: Context | None = None

    def generate(self, program) -> ProgramIR:
        """Traduza funções e comandos. Selecione expressões com DP."""
        self.program_ir = ProgramIR()
        for func in program.functions:
            self.statement(func)
        return self.program_ir

    def statement(self, node):
        """Traduza um comando ad hoc."""
        if isinstance(node, FunctionDecl):
            func_sym = node.metadata.get("symbol")
            if func_sym is None:
                func_sym = getattr(node, "symbol", None)
            self.function_ir = FunctionIR(function=func_sym)
            self.program_ir.functions.append(self.function_ir)
            self.context = Context(self.function_ir, self.program_ir)

            for i, p in enumerate(node.parameters):
                p_sym = p.metadata.get("symbol") or getattr(p, "symbol", None)
                p_vreg = self.context.variable(p_sym)
                self.context.emit(I.Param(dst=p_vreg, index=i, origin=p.span))

            self.statement(node.body)

            # Funções void devem terminar com Return(None) se caírem pelo fim
            if node.return_type == TypeName.VOID:
                if not (
                    self.function_ir.instructions
                    and isinstance(self.function_ir.instructions[-1], I.Return)
                ):
                    self.context.emit(I.Return(value=None, origin=node.span))

        elif isinstance(node, Block):
            for stmt in node.statements:
                self.statement(stmt)

        elif isinstance(node, VarDecl):
            if node.initializer is not None:
                val = self.expression(node.initializer, REG)
                var_sym = node.metadata.get("symbol") or getattr(node, "symbol", None)
                var_vreg = self.context.variable(var_sym)
                self.context.emit(I.Move(dst=var_vreg, src=val, origin=node.span))

        elif isinstance(node, Assignment):
            val = self.expression(node.value, REG)
            target_sym = node.target.metadata.get("symbol") or getattr(
                node.target, "symbol", None
            )
            var_vreg = self.context.variable(target_sym)
            self.context.emit(I.Move(dst=var_vreg, src=val, origin=node.span))

        elif isinstance(node, IfStmt):
            then_lbl = self.context.label()
            end_lbl = self.context.label()
            if node.else_block:
                else_lbl = self.context.label()
                self.expression(
                    node.condition, COND, true_label=then_lbl, false_label=else_lbl
                )
                self.context.emit(I.LabelInstr(label=then_lbl))
                self.statement(node.then_block)
                self.context.emit(I.Jump(target=end_lbl))
                self.context.emit(I.LabelInstr(label=else_lbl))
                self.statement(node.else_block)
                self.context.emit(I.LabelInstr(label=end_lbl))
            else:
                self.expression(
                    node.condition, COND, true_label=then_lbl, false_label=end_lbl
                )
                self.context.emit(I.LabelInstr(label=then_lbl))
                self.statement(node.then_block)
                self.context.emit(I.LabelInstr(label=end_lbl))

        elif isinstance(node, WhileStmt):
            test_lbl = self.context.label()
            body_lbl = self.context.label()
            exit_lbl = self.context.label()
            self.context.emit(I.LabelInstr(label=test_lbl))
            self.expression(
                node.condition, COND, true_label=body_lbl, false_label=exit_lbl
            )
            self.context.emit(I.LabelInstr(label=body_lbl))
            self.statement(node.body)
            self.context.emit(I.Jump(target=test_lbl))
            self.context.emit(I.LabelInstr(label=exit_lbl))

        elif isinstance(node, ReturnStmt):
            if node.value is not None:
                val = self.expression(node.value, REG)
                self.context.emit(I.Return(value=val, origin=node.span))
            else:
                self.context.emit(I.Return(value=None, origin=node.span))

        elif isinstance(node, CallStmt):
            self.expression(node.call, EFFECT)

        elif isinstance(node, PrintStmt):
            for item in node.items:
                if isinstance(item, StringLiteral):
                    sref = self.context.string(item.value)
                    self.context.emit(I.PrintString(string=sref, origin=item.span))
                else:
                    val = self.expression(item, REG)
                    t = item.metadata.get("type")
                    if t == TypeName.BOOL:
                        self.context.emit(I.PrintBool(value=val, origin=item.span))
                    else:
                        self.context.emit(I.PrintInt(value=val, origin=item.span))
            nl_ref = self.context.string("\n")
            self.context.emit(I.PrintString(string=nl_ref, origin=node.span))

    def expression(self, node, result_class, true_label=None, false_label=None):
        """Selecione e reconstrua uma expressão, preservando curto-circuito."""
        table = self.selector.analyze(node)
        return self._emit(node, result_class, table, true_label, false_label)

    def _emit(self, node, result_class, table, true_label=None, false_label=None):
        choice = table.lookup(node, result_class)
        if choice is None:
            raise RuntimeError(
                f"Sem cobertura para o nó {type(node).__name__} como {result_class}"
            )

        action = choice.rule.action

        # 1. Literais
        if action == "li_int":
            val = signed_literal(node)
            dst = self.context.temp()
            self.context.emit(I.Li(dst=dst, imm=val, origin=node.span))
            return dst

        if action == "li_bool":
            val = 1 if node.value else 0
            dst = self.context.temp()
            self.context.emit(I.Li(dst=dst, imm=val, origin=node.span))
            return dst

        # 2. Identificador
        if action == "id_reg":
            sym = node.metadata.get("symbol") or getattr(node, "symbol", None)
            return self.context.variable(sym)

        # 3. Imediatos sem instrução
        if action in ("imm12", "pow2"):
            return signed_literal(node)

        # 4. Negação aritmética
        if action == "neg":
            src = self._emit(node.operand, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Neg(dst=dst, src=src, origin=node.span))
            return dst

        # 5. Aritmética geral
        if action in ("add", "sub", "mul", "div", "rem"):
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            dst = self.context.temp()
            op_map = {
                "add": I.Add,
                "sub": I.Sub,
                "mul": I.Mul,
                "div": I.Div,
                "rem": I.Rem,
            }
            self.context.emit(op_map[action](dst=dst, lhs=lhs, rhs=rhs, origin=node.span))
            return dst

        # 6. Soma com imediato
        if action == "add_reg_imm":
            src = self._emit(node.left, REG, table)
            imm = signed_literal(node.right)
            dst = self.context.temp()
            self.context.emit(I.Addi(dst=dst, src=src, imm=imm, origin=node.span))
            return dst

        if action == "add_imm_reg":
            imm = signed_literal(node.left)
            src = self._emit(node.right, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Addi(dst=dst, src=src, imm=imm, origin=node.span))
            return dst

        # 7. Subtração com imediato invertido
        if action == "sub_reg_neg_imm":
            src = self._emit(node.left, REG, table)
            c = signed_literal(node.right)
            imm = -c
            dst = self.context.temp()
            self.context.emit(I.Addi(dst=dst, src=src, imm=imm, origin=node.span))
            return dst

        # 8. Multiplicação por potência de dois
        if action == "mul_reg_pow2":
            src = self._emit(node.left, REG, table)
            c = signed_literal(node.right)
            shift = c.bit_length() - 1
            dst = self.context.temp()
            self.context.emit(I.Slli(dst=dst, src=src, shift=shift, origin=node.span))
            return dst

        if action == "mul_pow2_reg":
            c = signed_literal(node.left)
            shift = c.bit_length() - 1
            src = self._emit(node.right, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Slli(dst=dst, src=src, shift=shift, origin=node.span))
            return dst

        # 9. Relacionais < e > para REG
        if action == "slt_less":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Slt(dst=dst, lhs=lhs, rhs=rhs, origin=node.span))
            return dst

        if action == "slt_greater":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Slt(dst=dst, lhs=rhs, rhs=lhs, origin=node.span))
            return dst

        # 10. Relacionais <= e >= para REG
        if action == "le_reg":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            t = self.context.temp()
            dst = self.context.temp()
            self.context.emit(I.Slt(dst=t, lhs=rhs, rhs=lhs, origin=node.span))
            self.context.emit(I.Seqz(dst=dst, src=t, origin=node.span))
            return dst

        if action == "ge_reg":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            t = self.context.temp()
            dst = self.context.temp()
            self.context.emit(I.Slt(dst=t, lhs=lhs, rhs=rhs, origin=node.span))
            self.context.emit(I.Seqz(dst=dst, src=t, origin=node.span))
            return dst

        # 11. Igualdade e desigualdade para REG
        if action == "eq_reg":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            t = self.context.temp()
            dst = self.context.temp()
            self.context.emit(I.Xor(dst=t, lhs=lhs, rhs=rhs, origin=node.span))
            self.context.emit(I.Seqz(dst=dst, src=t, origin=node.span))
            return dst

        if action == "ne_reg":
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            t = self.context.temp()
            dst = self.context.temp()
            self.context.emit(I.Xor(dst=t, lhs=lhs, rhs=rhs, origin=node.span))
            self.context.emit(I.Snez(dst=dst, src=t, origin=node.span))
            return dst

        # 12. Comparação relacional para COND
        if action in (
            "cond_less",
            "cond_greater",
            "cond_less_equal",
            "cond_greater_equal",
            "cond_equal",
            "cond_not_equal",
        ):
            lhs = self._emit(node.left, REG, table)
            rhs = self._emit(node.right, REG, table)
            if action == "cond_less":
                self.context.emit(
                    I.Blt(lhs=lhs, rhs=rhs, target=true_label, origin=node.span)
                )
            elif action == "cond_greater":
                self.context.emit(
                    I.Blt(lhs=rhs, rhs=lhs, target=true_label, origin=node.span)
                )
            elif action == "cond_less_equal":
                self.context.emit(
                    I.Bge(lhs=rhs, rhs=lhs, target=true_label, origin=node.span)
                )
            elif action == "cond_greater_equal":
                self.context.emit(
                    I.Bge(lhs=lhs, rhs=rhs, target=true_label, origin=node.span)
                )
            elif action == "cond_equal":
                self.context.emit(
                    I.Beq(lhs=lhs, rhs=rhs, target=true_label, origin=node.span)
                )
            elif action == "cond_not_equal":
                self.context.emit(
                    I.Bne(lhs=lhs, rhs=rhs, target=true_label, origin=node.span)
                )
            self.context.emit(I.Jump(target=false_label, origin=node.span))
            return None

        # 13. Negação lógica para REG
        if action == "not_reg":
            src = self._emit(node.operand, REG, table)
            dst = self.context.temp()
            self.context.emit(I.Seqz(dst=dst, src=src, origin=node.span))
            return dst

        # 14. Negação lógica para COND (inverte destinos)
        if action == "not_cond":
            self._emit(
                node.operand,
                COND,
                table,
                true_label=false_label,
                false_label=true_label,
            )
            return None

        # 15. && / || para COND
        if action == "and_cond":
            mid_lbl = self.context.label()
            self._emit(
                node.left, COND, table, true_label=mid_lbl, false_label=false_label
            )
            self.context.emit(I.LabelInstr(label=mid_lbl))
            self._emit(
                node.right, COND, table, true_label=true_label, false_label=false_label
            )
            return None

        if action == "or_cond":
            mid_lbl = self.context.label()
            self._emit(
                node.left, COND, table, true_label=true_label, false_label=mid_lbl
            )
            self.context.emit(I.LabelInstr(label=mid_lbl))
            self._emit(
                node.right, COND, table, true_label=true_label, false_label=false_label
            )
            return None

        # 16. && / || para REG
        if action in ("and_reg", "or_reg"):
            t_lbl = self.context.label()
            f_lbl = self.context.label()
            end_lbl = self.context.label()
            dst = self.context.temp()
            self._emit(node, COND, table, true_label=t_lbl, false_label=f_lbl)
            self.context.emit(I.LabelInstr(label=t_lbl))
            self.context.emit(I.Li(dst=dst, imm=1, origin=node.span))
            self.context.emit(I.Jump(target=end_lbl, origin=node.span))
            self.context.emit(I.LabelInstr(label=f_lbl))
            self.context.emit(I.Li(dst=dst, imm=0, origin=node.span))
            self.context.emit(I.LabelInstr(label=end_lbl))
            return dst

        # 17. Literal bool para COND
        if action == "bool_cond":
            target = true_label if node.value else false_label
            self.context.emit(I.Jump(target=target, origin=node.span))
            return None

        # 18. Identificador bool para COND
        if action == "id_cond":
            sym = node.metadata.get("symbol") or getattr(node, "symbol", None)
            vreg = self.context.variable(sym)
            self.context.emit(I.Bnez(src=vreg, target=true_label, origin=node.span))
            self.context.emit(I.Jump(target=false_label, origin=node.span))
            return None

        # 19. Chamada de função para REG ou EFFECT
        if action == "call_reg":
            func_sym = getattr(node, "function", None) or node.metadata.get("symbol")
            args_vregs = [self._emit(arg, REG, table) for arg in node.arguments]
            dst = self.context.temp()
            self.context.emit(
                I.Call(
                    dst=dst,
                    function=func_sym,
                    args=args_vregs,
                    origin=node.span,
                )
            )
            return dst

        if action == "call_effect":
            func_sym = getattr(node, "function", None) or node.metadata.get("symbol")
            args_vregs = [self._emit(arg, REG, table) for arg in node.arguments]
            self.context.emit(
                I.Call(
                    dst=None,
                    function=func_sym,
                    args=args_vregs,
                    origin=node.span,
                )
            )
            return None

        # 20. Chamada de função bool para COND
        if action == "call_cond":
            func_sym = getattr(node, "function", None) or node.metadata.get("symbol")
            args_vregs = [self._emit(arg, REG, table) for arg in node.arguments]
            dst = self.context.temp()
            self.context.emit(
                I.Call(
                    dst=dst,
                    function=func_sym,
                    args=args_vregs,
                    origin=node.span,
                )
            )
            self.context.emit(I.Bnez(src=dst, target=true_label, origin=node.span))
            self.context.emit(I.Jump(target=false_label, origin=node.span))
            return None

        raise NotImplementedError(f"Ação não implementada: {action}")
