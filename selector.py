"""Ponto de implementação do reconhecimento de padrões e custos mínimos com DP."""

from patterns import (
    Args,
    Choice,
    Need,
    Pattern,
    SelectionTable,
    children as ast_children,
)


class Selector:
    """Selecione coberturas sem executar expressões ou emitir instruções."""

    def __init__(self, rules):
        self.rules = tuple(rules)

    def analyze(self, expr):
        """Calcule mínimos por nó/classe sem emitir instruções."""
        table = SelectionTable()
        self._post_order(expr, table)
        return table

    def _post_order(self, node, table):
        # 1. Visita filhos em pós-ordem
        for child in ast_children(node):
            self._post_order(child, table)

        # 2. Testa todas as regras aplicáveis e calcula o custo mínimo por classe
        best_choices = {}  # result_class -> Choice

        for rule in self.rules:
            match = self._match(node, rule.pattern, table)
            if match is None:
                continue
            sub_cost, subproblems = match
            total_cost = rule.cost + sub_cost

            current_best = best_choices.get(rule.result)
            if current_best is None or total_cost < current_best.cost:
                best_choices[rule.result] = Choice(total_cost, rule, subproblems)

        for result_class, choice in best_choices.items():
            table.put(node, result_class, choice)

    def _match(self, node, pattern, table):
        if pattern.kind is not None and not isinstance(node, pattern.kind):
            return None
        if pattern.operator is not None and getattr(node, "operator", None) is not pattern.operator:
            return None
        if pattern.predicate is not None and not pattern.predicate(node):
            return None

        # Padrão sem filhos: não possui subproblemas
        if not pattern.children:
            return (0, ())

        # Padrão com Args (chamadas de função de aridade arbitrária)
        if len(pattern.children) == 1 and isinstance(pattern.children[0], Args):
            req_class = pattern.children[0].result
            args = getattr(node, "arguments", ())
            subproblems = []
            cost = 0
            for arg in args:
                choice = table.lookup(arg, req_class)
                if choice is None:
                    return None
                cost += choice.cost
                subproblems.append((arg, req_class))
            return (cost, tuple(subproblems))

        node_kids = ast_children(node)
        if len(node_kids) != len(pattern.children):
            return None

        cost = 0
        subproblems = []
        for kid, pat_child in zip(node_kids, pattern.children):
            if isinstance(pat_child, Need):
                choice = table.lookup(kid, pat_child.result)
                if choice is None:
                    return None
                cost += choice.cost
                subproblems.append((kid, pat_child.result))
            elif isinstance(pat_child, Pattern):
                sub_match = self._match(kid, pat_child, table)
                if sub_match is None:
                    return None
                sub_cost, sub_probs = sub_match
                cost += sub_cost
                subproblems.extend(sub_probs)
            else:
                return None

        return (cost, tuple(subproblems))
