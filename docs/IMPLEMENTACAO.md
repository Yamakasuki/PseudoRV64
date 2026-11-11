# Documentação Técnica e de Implementação — pseudoRV64 (Etapa 6)

## 1. Visão Geral da Arquitetura

A Etapa 6 traduz a AST tipada e validada do compilador MicroC em uma representação intermediária linear executável (**pseudoRV64**).

### Componentes Fundamentais da IR:
- **`ProgramIR`**: Raiz do programa, contendo `functions` (lista de `FunctionIR`) e `strings` (pool global `dict[StringRef, str]`).
- **`FunctionIR`**: Representa uma função contendo o símbolo proprietário (`FunctionSymbol`) e a sequência ordenada de instruções (`instructions`).
- **`VReg`**: Registrador virtual de 64 bits com sinal. Cada registrador possui identidade única e é local à sua função (`VReg(owner, id)`). Não há limite no número de registradores virtuais nesta etapa.
- **`Label`**: Rótulo local de salto/desvio com escopo fechado à função (`Label(owner, id)`).
- **`StringRef`**: Referência opaca a uma string decodificada no pool do programa.

---

## 2. Catálogo de Seleção de Instruções (`catalogue.py`)

O catálogo normativo implementa 20 famílias de regras de casamento de padrões em árvore (*tree-pattern matching*).

| Família | Nome da Regra | Classe | Custo | Padrão / Condição | Ação Emissora |
| :---: | :--- | :---: | :---: | :--- | :--- |
| **1** | `int_literal_reg` | `REG` | 1 | `signed_literal(n) is not None` | `Li(dst, imm)` |
| **1** | `bool_literal_reg` | `REG` | 1 | `BoolLiteral` | `Li(dst, 1/0)` |
| **2** | `id_reg` | `REG` | 0 | `IdentifierExpr` | Reutiliza `variable(sym)` |
| **3** | `imm12` | `IMM12` | 0 | `imm12(n)` ($-2048 \le n \le 2047$) | Sem instrução |
| **3** | `pow2` | `POW2` | 0 | `pow2(n)` ($n = 2^k, k \ge 0$) | Sem instrução |
| **4** | `neg_reg` | `REG` | 1 | `UnaryExpr(NEGATE, Need(REG))` | `Neg(dst, src)` |
| **5** | `add_reg`, `sub_reg`, `mul_reg`, `div_reg`, `rem_reg` | `REG` | 1 | `BinaryExpr(OP, Need(REG), Need(REG))` | `Add`, `Sub`, `Mul`, `Div`, `Rem` |
| **6** | `add_reg_imm` / `add_imm_reg` | `REG` | 1 | `BinaryExpr(ADD, Need(REG), Need(IMM12))` | `Addi(dst, src, imm)` |
| **7** | `sub_reg_neg_imm` | `REG` | 1 | `BinaryExpr(SUB, Need(REG), neg_imm12)` | `Addi(dst, src, -c)` |
| **8** | `mul_reg_pow2` / `mul_pow2_reg` | `REG` | 1 | `BinaryExpr(MUL, Need(REG), Need(POW2))` | `Slli(dst, src, k)` |
| **9** | `slt_less` / `slt_greater` | `REG` | 1 | `BinaryExpr(< ou >, Need(REG), Need(REG))` | `Slt` direto ou com operandos invertidos |
| **10** | `le_reg` / `ge_reg` | `REG` | 2 | `BinaryExpr(<= ou >=, Need(REG), Need(REG))` | `Slt` seguido de `Seqz` |
| **11** | `eq_reg` / `ne_reg` | `REG` | 2 | `BinaryExpr(== ou !=, Need(REG), Need(REG))` | `Xor` seguido de `Seqz` ou `Snez` |
| **12** | `cond_*` (6 relacionais) | `COND` | 2 | `BinaryExpr(REL, Need(REG), Need(REG))` | Branch direto (`Blt`, `Bge`, `Beq`, `Bne`) + `Jump false_label` |
| **13** | `not_reg` | `REG` | 1 | `UnaryExpr(NOT, Need(REG))` | `Seqz(dst, src)` |
| **14** | `not_cond` | `COND` | 0 | `UnaryExpr(NOT, Need(COND))` | Inverte `true_label` $\leftrightarrow$ `false_label` |
| **15** | `and_cond` / `or_cond` | `COND` | 0 | `BinaryExpr(&&/\|\|, Need(COND), Need(COND))` | Encadeamento de controle com label intermediário |
| **16** | `and_reg` / `or_reg` | `REG` | 3 | `BinaryExpr(&&/\|\|, Need(COND), Need(COND))` | Avaliação em `COND` + `Li 1` + `Jump` + `Li 0` |
| **17** | `bool_cond` | `COND` | 1 | `BoolLiteral` | `Jump true_label` ou `Jump false_label` |
| **18** | `id_cond` | `COND` | 2 | `IdentifierExpr (bool)` | `Bnez(vreg, true_label)` + `Jump false_label` |
| **19** | `call_reg` / `call_effect` | `REG`/`EFFECT` | 1 | `CallExpr(Args(REG))` | `Call(dst, fn, args)` / `Call(None, fn, args)` |
| **20** | `call_cond` | `COND` | 3 | `CallExpr (bool)(Args(REG))` | `Call(t, fn, args)` + `Bnez` + `Jump false_label` |

---

## 3. Algoritmo de Casamento e Programação Dinâmica (`selector.py`)

O seletor resolve o problema da cobertura de custo mínimo em árvores:
1. **Percurso em pós-ordem**: Garante que todas as subárvores de um nó já possuam suas soluções memorizadas em `SelectionTable`.
2. **Custo Aditivo Ótimo**:
   $$C_{total}(node, c) = \text{cost}(rule) + \sum_{(child_i, c_i) \in subproblems} C(child_i, c_i)$$
3. **Desempate Estável**: Quando duas regras aplicáveis possuem custos idênticos, a primeira regra definida no catálogo é preservada, garantindo determinismo estrito.

---

## 4. Gerador de Código (`codegen.py`)

- **Comandos *ad hoc*:**
  - `FunctionDecl`: Aloca contexto e emite obrigatoriamente a sequência ordenada `Param(dst=variable(p), index=i)` para cada parâmetro. Emite `Return(None)` ao final de funções `void`.
  - `VarDecl` e `Assignment`: Avaliam a expressão como `REG` e emitem `Move` para o registrador da variável.
  - `IfStmt` e `WhileStmt`: Conectam blocos básicos através de rótulos locais e saltos incondicionais de convergência.
  - `PrintStmt`: Processa itens da esquerda para a direita, emitindo `PrintInt`, `PrintBool` ou `PrintString`, finalizando com a quebra compartilhada `\n` via `Context.string`.
- **Curto-Circuito em Expressões Lógicas:**
  - Em `a && b`, o segundo operando só é alcançado se o primeiro for verdadeiro.
  - Em `a || b`, o segundo operando só é alcançado se o primeiro for falso.
  - Nenhuma instrução dos operandos é pré-computada em bloco antes dos saltos.

---

## 5. Validação e Testes

Todos os 87 testes públicos oficiais (`tests/test_infrastructure.py`, `tests/test_codegen.py`, `tests/test_public_scenarios.py`) foram aprovados:
```sh
pytest tests/ -v
python run_tests.py
```
Desempenho da execução: **100% aprovado em 0,28s**.
