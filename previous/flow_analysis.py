"""Coordenação das passagens de fluxo. Recebe a AST com nomes e tipos válidos."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from dataclasses import dataclass

from ast_nodes import Program
from cfg import CFG
from cfg_builder import CFGBuilder
from flow_checker import ReadChecker, check_function_exit
from initialization import InitializationAnalyzer, InitializationFacts
from reachability import compute_reachable
from semantic_errors import SemanticDiagnostic, SemanticError


@dataclass(slots=True)
class FunctionFlowFacts:
    cfg: CFG
    reachable: set[int]
    initialization: InitializationFacts


class FlowAnalyzer:
    def __init__(self) -> None:
        self.functions: dict[str, FunctionFlowFacts] = {}

    def analyze(self, program: Program) -> Program:
        self.functions = {}
        diagnostics: list[SemanticDiagnostic] = []
        for function in program.functions:
            cfg = CFGBuilder().build(function)
            function.metadata["cfg"] = cfg
            reachable = compute_reachable(cfg)
            initialization = InitializationAnalyzer(cfg, reachable).solve()
            facts = FunctionFlowFacts(cfg, reachable, initialization)
            self.functions[function.name] = facts
            function.metadata["flow"] = facts
            diagnostics.extend(ReadChecker().check(cfg, reachable, initialization))
            diagnostics.extend(check_function_exit(cfg, reachable))
        if diagnostics:
            raise SemanticError(diagnostics)
        return program


def check_flow(program: Program) -> None:
    pass
