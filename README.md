# Projeto de Compiladores — Etapa 6: Geração de pseudoRV64 e Seleção de Instruções

Este repositório contém a implementação da **Etapa 6** do compilador da linguagem **MicroC**: a geração de código intermediário linear de baixo nível na arquitetura **pseudoRV64** e a seleção ótima de instruções sobre expressões via casamento de padrões em árvores (*Tree Pattern Matching*) com **Programação Dinâmica (DP)** em pós-ordem (*bottom-up*).

A especificação normativa de referência para a arquitetura pseudoRV64, catálogo de regras, custos e modelo de execução é o [ENUNCIADO.pdf](ENUNCIADO.pdf), em conjunto com a especificação da linguagem MicroC.

---

## Sumário

- [Visão Geral e Objetivos](#visão-geral-e-objetivos)
- [O Frontend em `previous/`](#o-frontend-em-previous)
- [Estrutura do Repositório](#estrutura-do-repositório)
- [Módulos Implementados pelo Grupo](#módulos-implementados-pelo-grupo)
  - [Catálogo de Regras (`catalogue.py`)](#catálogo-de-regras-cataloguepy)
  - [Seletor de Instruções por DP (`selector.py`)](#seletor-de-instruções-por-dp-selectorpy)
  - [Gerador de Código e Curto-Circuito (`codegen.py`)](#gerador-de-código-e-curto-circuito-codegenpy)
  - [Modelo de IR, Executor e Padrões (`ir.py`, `executor.py`, `patterns.py`)](#modelo-de-ir-executor-e-padrões-irpy-executorpy-patternspy)
- [Preparação do Ambiente e Execução](#preparação-do-ambiente-e-execução)
- [Exemplos Oficiais e Análise de Saída](#exemplos-oficiais-e-análise-de-saída)
  - [1. Seleção Ótima (`examples/selecao.mc`)](#1-seleção-ótima-examplesselecaomc)
  - [2. Curto-Circuito e Efeitos Colaterais (`examples/curto_circuito.mc`)](#2-curto-circuito-e-efeitos-colaterais-examplescurto_circuitomc)
  - [3. Fluxo Integrado e Potência de Dois (`examples/integrado.mc`)](#3-fluxo-integrado-e-potência-de-dois-examplesintegradomc)
- [Suíte de Testes e Validação](#suíte-de-testes-e-validação)
- [Checklist de Conclusão e Entrega](#checklist-de-conclusão-e-entrega)

---

## Visão Geral e Objetivos

A pseudoRV64 é uma representação intermediária linear e executável inspirada no conjunto de instruções RISC-V de 64 bits (RV64I/M). Ela abstrai restrições físicas de hardware mantendo um modelo próximo da máquina-alvo:
- **Registradores Virtuais Ilimitados (`VReg`)**: identificados por números inteiros sequenciais vinculados localmente a cada função proprietária (`v0`, `v1`, ...).
- **Rótulos Locais (`Label`)**: alvos de desvio exclusivos à função (`L0`, `L1`, ...).
- **Pool Global de Strings (`StringRef`)**: gerenciamento centralizado e imutável de literais de texto compartilhados (`str0`, `str1`, ...).
- **Instruções Pseudo-RISC-V**: 22 instruções canônicas que cobrem operações aritméticas, lógicas, imediatos de 12 bits, desvios condicionais (`beq`, `bne`, `blt`, `bge`, `beqz`, `bnez`), saltos incondicionais (`j`), passagem de parâmetros (`param`), chamadas (`call`), retorno (`return`) e entrada/saída básica (`print_int`, `print_bool`, `print_string`).

Nesta etapa, o pipeline divide a geração em duas abordagens complementares:
1. **Comandos de controle e escopo (Geração Ad Hoc)**: traduzidos diretamente em `codegen.py`, gerando a topologia de rótulos e desvios para condicionais (`if`), laços (`while`), atribuições, declarações e chamadas em nível de comando.
2. **Expressões (Seleção Ótima com DP)**: cada árvore sintática de expressão é analisada em pós-ordem por `selector.py` contra o catálogo fechado de 20 famílias normativas em `catalogue.py`, cobrindo os nós com custo mínimo antes de emitir as instruções de cálculo ou desvio.

---

## O Frontend em `previous/`

Para alimentar o gerador de código sem duplicar nem divergir das etapas anteriores, toda a base do compilador foi consolidada na pasta `previous/`:
- **Análise Léxica (Etapa 1)**: `Lexer.py`, `microc_automato.py` (autômato dirigido por tabela) e `microc_cursor.py` (rastreamento de linha e coluna).
- **Análise Sintática (Etapa 3)**: `parser.py` (parser preditivo por descida recursiva LL(1)), `ast_nodes.py` (nós canônicos da AST) e `ast_printer.py` (visualização em texto e Graphviz DOT).
- **Análise Semântica 1 (Etapa 4)**: `symbols.py` (tabela de símbolos e escopos léxicos aninhados), `name_resolver.py` (ligação de identificadores), `type_checker.py` (checagem de tipos primitivos `int`, `bool`, `void`) e `visitor.py`.
- **Análise Semântica 2 (Etapa 5)**: `cfg.py`, `cfg_builder.py`, `reachability.py`, `initialization.py` e `flow_checker.py` (verificação de inicialização definida e retorno obrigatório).

O módulo `load_previous.py` atua na inicialização ajustando dinamicamente o `sys.path`. Ele garante que todos os módulos acessem as mesmas classes fundamentais (`Program`, `SourceSpan`, `SymbolKind`, etc.), sem criar tipos duplicados ou wrappers incompatíveis.

> **Regra de Execução do Pipeline**: Nenhum código intermediário é gerado se o programa contiver erros léxicos, sintáticos ou semânticos. Nesses casos, o runner aborta imediatamente com código de saída 1.

---

## Estrutura do Repositório

```text
.
├── catalogue.py               # Catálogo fechado de 20 famílias normativas e predicados
├── codegen.py                 # Gerador de código, comandos ad hoc e curto-circuito
├── ENUNCIADO.pdf              # Especificação oficial e normativa da Etapa 6
├── examples/                  # Programas MicroC de exemplo fornecidos
│   ├── curto_circuito.mc      # Avaliação em curto-circuito com chamadas e efeitos
│   ├── integrado.mc           # Programa completo (while, slli, chamadas, curto-circuito)
│   └── selecao.mc             # Seleção de addi sobre constante imediata
├── executor.py                # Validador de IR e interpretador virtual de 64 bits
├── ir.py                      # Modelo formal de pseudoRV64, VReg, Context e formatador
├── load_previous.py           # Carregador transparente do frontend em previous/
├── patterns.py                # Modelo de regras, classes de resultado e SelectionTable
├── previous/                  # Módulos históricos consolidados do grupo
│   ├── ast_nodes.py           # Hierarquia formal de nós da AST MicroC
│   ├── ast_printer.py         # Impressão textual e exportação DOT da AST
│   ├── cfg_builder.py         # Construtor de CFG da Semântica 2
│   ├── cfg.py                 # Estruturas de blocos básicos e fluxo de controle
│   ├── flow_analysis.py       # Coordenação das análises de fluxo
│   ├── flow_checker.py        # Verificação de inicialização e retornos
│   ├── initialization.py      # Análise de ponto fixo de inicialização definida
│   ├── Lexer.py               # Lexer completo do grupo (Etapa 1)
│   ├── microc_automato.py     # Autômato finito determinístico com tabelas
│   ├── microc_cursor.py       # Navegador de cursor com coordenadas
│   ├── name_resolver.py       # Resolução de nomes e escopos léxicos
│   ├── parser.py              # Parser LL(1) recursivo descendente do grupo (Etapa 3)
│   ├── reachability.py        # Análise de alcançabilidade de blocos básicos
│   ├── semantic_errors.py     # Hierarquia de diagnósticos semânticos
│   ├── semantic.py            # Coordenador semântico das Etapas 4 e 5
│   ├── symbols.py             # Tabela de símbolos e escopos normativos
│   ├── type_checker.py        # Verificador estático de tipos
│   └── visitor.py             # Padrão visitante base da AST
├── pyproject.toml             # Metadados do projeto Python
├── README.md                  # Documentação executiva e técnica da Etapa 6
├── requirements-dev.txt       # Dependências de desenvolvimento (pytest)
├── runner.py                  # Ponto de entrada CLI (geração, dump e execução)
├── run_tests.py               # Executor da suíte de testes com geração de relatório JSON
├── selector.py                # Algoritmo de casamento de padrões e DP em pós-ordem
└── tests/                     # Suíte de testes automatizados
    ├── conftest.py            # Fixtures do pytest
    ├── test_codegen.py        # Testes de geração e avaliação básica de expressões
    ├── test_infrastructure.py # Validação das estruturas de IR e interpretador
    └── test_public_scenarios.py # 87 cenários públicos de seleção e comportamento
```

---

## Módulos Implementados pelo Grupo

### Catálogo de Regras (`catalogue.py`)

O catálogo é uma tupla imutável com as **20 famílias normativas** especificadas na Seção 7 do enunciado. Cada família descreve:
- Uma classe de resultado desejada (`REG`, `COND`, `IMM12`, `POW2`, `EFFECT`).
- Um padrão de árvore com restrições sintáticas e semânticas.
- O custo próprio da regra.
- O identificador da ação que materializará as instruções em `codegen.py`.

| Família | Nome da Regra | Resultado | Padrão da AST / Predicado | Custo | Ação Emissora / Instruções |
|---|---|:---:|---|:---:|---|
| **1** | `int_literal_reg`<br>`bool_literal_reg` | `REG` | `IntLiteral` (ou `UnaryExpr(-, IntLiteral)`)<br>`BoolLiteral` | 1 | `li_int` (`li dst, imm`)<br>`li_bool` (`li dst, 0/1`) |
| **2** | `id_reg` | `REG` | `IdentifierExpr` | 0 | `id_reg` (reutiliza `VReg` único do símbolo) |
| **3** | `imm12`<br>`pow2` | `IMM12`<br>`POW2` | `signed_literal ∈ [-2048, 2047]`<br>`signed_literal ∈ (0, 2^62] ∧ pot2` | 0 | `imm12` (sem instrução)<br>`pow2` (sem instrução) |
| **4** | `neg_reg` | `REG` | `UnaryExpr(-, Need(REG))` | 1 | `neg` (`neg dst, src`) |
| **5** | `add_reg`, `sub_reg`<br>`mul_reg`, `div_reg`<br>`rem_reg` | `REG` | `BinaryExpr(+, -, *, /, %, Need(REG), Need(REG))` | 1 | `add`, `sub`, `mul`, `div`, `rem`<br>(`op dst, lhs, rhs`) |
| **6** | `add_reg_imm`<br>`add_imm_reg` | `REG` | `BinaryExpr(+, Need(REG), Need(IMM12))`<br>`BinaryExpr(+, Need(IMM12), Need(REG))` | 1 | `add_reg_imm`<br>`add_imm_reg` (`addi dst, src, imm`) |
| **7** | `sub_reg_neg_imm` | `REG` | `BinaryExpr(-, Need(REG), neg_imm12)` | 1 | `sub_reg_neg_imm` (`addi dst, src, -imm`) |
| **8** | `mul_reg_pow2`<br>`mul_pow2_reg` | `REG` | `BinaryExpr(*, Need(REG), Need(POW2))`<br>`BinaryExpr(*, Need(POW2), Need(REG))` | 1 | `mul_reg_pow2`<br>`mul_pow2_reg` (`slli dst, src, shift`) |
| **9** | `slt_less`<br>`slt_greater` | `REG` | `BinaryExpr(<, Need(REG), Need(REG))`<br>`BinaryExpr(>, Need(REG), Need(REG))` | 1 | `slt_less` (`slt dst, lhs, rhs`)<br>`slt_greater` (`slt dst, rhs, lhs`) |
| **10** | `le_reg`<br>`ge_reg` | `REG` | `BinaryExpr(<=, Need(REG), Need(REG))`<br>`BinaryExpr(>=, Need(REG), Need(REG))` | 2 | `le_reg` (`slt t, rhs, lhs; seqz dst, t`)<br>`ge_reg` (`slt t, lhs, rhs; seqz dst, t`) |
| **11** | `eq_reg`<br>`ne_reg` | `REG` | `BinaryExpr(==, Need(REG), Need(REG))`<br>`BinaryExpr(!=, Need(REG), Need(REG))` | 2 | `eq_reg` (`xor t, lhs, rhs; seqz dst, t`)<br>`ne_reg` (`xor t, lhs, rhs; snez dst, t`) |
| **12** | `cond_less`<br>`cond_greater`<br>`cond_less_equal`<br>`cond_greater_equal`<br>`cond_equal`<br>`cond_not_equal` | `COND` | `BinaryExpr(rel_op, Need(REG), Need(REG))` | 2 | `cond_*` (desvio condicional `blt`/`bge`/`beq`/`bne` para `true_label` + `j false_label`) |
| **13** | `not_reg` | `REG` | `UnaryExpr(!, Need(REG))` | 1 | `not_reg` (`seqz dst, src`) |
| **14** | `not_cond` | `COND` | `UnaryExpr(!, Need(COND))` | 0 | `not_cond` (inverte `true_label` e `false_label`) |
| **15** | `and_cond`<br>`or_cond` | `COND` | `BinaryExpr(&& / \|\|, Need(COND), Need(COND))` | 0 | `and_cond`, `or_cond` (curto-circuito puro via rótulos intermediários) |
| **16** | `and_reg`<br>`or_reg` | `REG` | `BinaryExpr(&& / \|\|, Need(COND), Need(COND))` | 3 | `and_reg`, `or_reg` (avalia em `COND` e materializa `1` ou `0` com `li` + `j`) |
| **17** | `bool_cond` | `COND` | `BoolLiteral` | 1 | `bool_cond` (`j true_label` ou `j false_label`) |
| **18** | `id_cond` | `COND` | `IdentifierExpr (bool)` | 2 | `id_cond` (`bnez vreg, true_label; j false_label`) |
| **19** | `call_reg`<br>`call_effect` | `REG`<br>`EFFECT` | `CallExpr(Args(REG))` com retorno não-void<br>`CallExpr(Args(REG))` em comando | 1 | `call_reg` (`call dst, fn, [args]`)<br>`call_effect` (`call None, fn, [args]`) |
| **20** | `call_cond` | `COND` | `CallExpr(Args(REG))` com retorno bool | 3 | `call_cond` (`call dst, fn, [args]; bnez dst, true_label; j false_label`) |

#### Predicados e Reconhecimento Imediato
- `signed_literal(node)`: reconhece inteiros literais ou negações imediatas (`-c`), sem executar *constant folding* em subexpressões compostas.
- `imm12(node)`: valida o intervalo de 12 bits com sinal `[-2048, 2047]`.
- `neg_imm12(node)`: reconhece valores literais cujo oposto `-n` cabe em 12 bits (usado para converter `x - c` em `addi x, -c`).
- `pow2(node)`: reconhece potências estritas de 2 no intervalo `(0, 2^62]`, calculando `shift = c.bit_length() - 1` para emissão de `slli`.

---

### Seletor de Instruções por DP (`selector.py`)

A classe `Selector` implementa o casamento de padrões por programação dinâmica *bottom-up*:
1. **Percurso Pós-Ordem**: a função recursiva `_post_order(node, table)` primeiro visita e seleciona as melhores coberturas para todos os filhos de `node`.
2. **Matching de Padrões (`_match`)**:
   - Confere a classe do nó (`kind`) e o operador sintático (`operator`).
   - Avalia predicados semânticos auxiliares (ex.: conferir se um identificador ou chamada retorna booleano).
   - Valida recursivamente os requisitos de cada filho:
     - `Need(result_class)`: consulta em `SelectionTable` se a subárvore já possui uma cobertura válida para `result_class`.
     - `Args(result_class)`: itera sobre todos os argumentos de uma chamada de função (aridade arbitrária), acumulando o custo de cada argumento em `REG`.
     - `Pattern(...)`: casamento aninhado para literais compostos.
3. **Memorização Ótima (`SelectionTable`)**:
   - Para cada classe de resultado (`REG`, `COND`, etc.), calcula o custo total acumulado:
     $$\text{Custo Total} = \text{Custo da Regra} + \sum \text{Custo dos Subproblemas}$$
   - Registra apenas a melhor escolha (`Choice`), contendo o custo mínimo, a regra vencedora e as dependências `(filho, classe_exigida)`.
   - Indexação segura por `(id(node), ResultClass)`, mantendo referências fortes aos nós para garantir a unicidade de seus identificadores durante toda a análise.

---

### Gerador de Código e Curto-Circuito (`codegen.py`)

O módulo `CodeGenerator` atua como a espinha dorsal da tradução, combinando comandos e expressões:

#### 1. Comandos Ad Hoc (`statement`)
- **Declaração de Funções (`FunctionDecl`)**: instancia `FunctionIR` e `Context`. Para cada parâmetro formal na posição $i$, emite `Param(dst=vreg, index=i)`, garantindo que parâmetros fiquem disponíveis em registradores virtuais dedicados. Funções `void` recebem automaticamente um `Return(None)` ao final caso a execução atinja a borda do bloco.
- **Declarações e Atribuições (`VarDecl`, `Assignment`)**: seleciona a expressão da direita em `REG` e emite `Move(dst=var_vreg, src=val)`.
- **Condicionais e Laços (`IfStmt`, `WhileStmt`)**:
  - Aloca rótulos com `context.label()`.
  - A condição é avaliada em modo `COND`, fornecendo `true_label` e `false_label`.
  - Emite `LabelInstr` e `Jump` organizando os caminhos verdadeiro, falso e junção sem materializar variáveis booleanas desnecessárias na memória.
- **Impressão (`PrintStmt`)**:
  - Para strings literais, registra o conteúdo no pool compartilhado e emite `PrintString(string=sref)`.
  - Para expressões inteiras ou booleanas, seleciona em `REG` e emite `PrintInt` ou `PrintBool`.
  - Toda instrução `print(...)` encerra emitindo um `PrintString` com a quebra de linha `\n`.

#### 2. Reconstrução e Curto-Circuito (`expression` e `_emit`)
- **Curto-Circuito Puro (`and_cond`, `or_cond`)**:
  - Em `a && b`, o operando esquerdo `a` recebe como alvos `(mid_lbl, false_label)`. Somente se `a` for verdadeiro o fluxo atinge `mid_lbl`, onde `b` é avaliado com `(true_label, false_label)`.
  - Em `a || b`, o operando esquerdo recebe `(true_label, mid_lbl)`. Se `a` for verdadeiro, desvia imediatamente para `true_label`; caso contrário, testa `b`.
  - Custo próprio: 0 instruções extras.
- **Materialização de Booleanos (`and_reg`, `or_reg`)**:
  - Quando uma operação lógica precisa produzir um valor concreto em registrador virtual (ex.: `bool x = a && b;`), a expressão é selecionada em modo `COND` contra dois rótulos locais: `t_lbl` e `f_lbl`.
  - Em `t_lbl`, emite `li dst, 1` seguido de `j end_lbl`. Em `f_lbl`, emite `li dst, 0`.
- **Negação Lógica em Condição (`not_cond`)**:
  - Inverte diretamente os argumentos `true_label` e `false_label` na chamada recursiva do operando, eliminando desvios redundantes a custo zero.
- **Identidade de Variáveis e Sombreamento**:
  - O método `Context.variable(symbol)` mapeia cada objeto `Symbol` único ao seu respectivo `VReg`. Dessa forma, variáveis homônimas em escopos léxicos distintos (sombreamento/shadowing) recebem registradores virtuais independentes sem risco de colisão.

---

### Modelo de IR, Executor e Padrões (`ir.py`, `executor.py`, `patterns.py`)

- **`ir.py`**:
  - Define as entidades fundamentais `VReg(owner, id)`, `Label(owner, id)` e `StringRef(id)`.
  - Gera via metaprogramação com dataclasses congeladas as 22 instruções da arquitetura (`Li`, `Move`, `Neg`, `Add`, `Sub`, `Mul`, `Div`, `Rem`, `Addi`, `Slli`, `Slt`, `Xor`, `Seqz`, `Snez`, `LabelInstr`, `Jump`, `Beq`, `Bne`, `Blt`, `Bge`, `Beqz`, `Bnez`, `Param`, `Call`, `Return`, `PrintInt`, `PrintBool`, `PrintString`).
  - Funções de análise de dados `uses(ins)` e `defs(ins)`, que inspecionam os registradores lidos e escritos por instrução (suporte para alocadores de registradores posteriores).
  - Formatador textual `format_ir(program)`, produzindo a sintaxe próxima ao assembly RV64 para inspeção.
- **`executor.py`**:
  - Função `validate(program)`: confere rigorosamente se todas as referências de registradores e rótulos pertencem à respectiva função proprietária, se imediatos estão dentro dos limites de 12 e 64 bits e se os destinos de desvio existem.
  - Classe `Interpreter`: simula uma máquina virtual determinística de 64 bits com aritmética com sinal e divisão truncada para zero conforme a ISO C / RISC-V. Captura a saída do programa (`stdout`) e expõe o retorno final de `main`.
- **`patterns.py`**:
  - Define o vocabulário formal de seleção: `ResultClass`, `Need`, `Args`, `Pattern`, `Rule` e `Choice`.

---

## Preparação do Ambiente e Execução

O ambiente de referência oficial é **Python 3.12**.

### 1. Criação e Ativação do Ambiente Virtual

No Linux / macOS:
```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

No Windows (PowerShell):
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

---

### 2. Modos de Execução com o `runner.py`

O script `runner.py` integra o pipeline completo (Lexer → Parser → Semântica 1 & 2 → CodeGenerator → Validador de IR → Interpretador):

#### A. Visualização da Representação Intermediária (`--dump-ir` ou padrão)
```sh
python runner.py examples/selecao.mc --dump-ir
```

#### B. Execução e Emissão da Saída (`--run`)
```sh
python runner.py examples/selecao.mc --run
```

#### C. Limitação de Passos de Execução (`--max-steps`)
Para mitigar laços infinitos ou limitar a execução:
```sh
python runner.py examples/integrado.mc --run --max-steps 50000
```

#### Códigos de Saída do Runner:
| Código | Significado |
|:---:|---|
| **0** | Sucesso completo no modo solicitado. |
| **1** | Falha no frontend: erro léxico, sintático ou semântico (com diagnóstico exibido). |
| **2** | Erro de uso da CLI ou leitura do arquivo-fonte. |
| **3** | Ponto de extensão pendente (`NotImplementedError`). |
| **4** | IR estruturalmente inválida ou erro em tempo de execução (ex.: divisão por zero). |

---

## Exemplos Oficiais e Análise de Saída

### 1. Seleção Ótima (`examples/selecao.mc`)

O exemplo demonstra como o seletor opta por uma instrução especializada com imediato em vez de carregar a constante em um registrador separado:

```c
int incrementar(int x) {
    return x + 5;
}

int main() {
    print(incrementar(7));
    return 0;
}
```

#### Saída da IR (`python runner.py examples/selecao.mc --dump-ir`):
```text
.strings
str0: "\n"

incrementar:
  param v0, 0
  addi v1, v0, 5
  return v1
main:
  li v0, 7
  call v1, incrementar, [v0]
  print_int v1
  print_string str0
  li v2, 0
  return v2
```

> **Análise de Custos**: Para `x + 5`, uma estratégia ingênua emitiria `li v_tmp, 5` (custo 1) + `add v1, v0, v_tmp` (custo 1), somando custo 2. O seletor casa a regra `add_reg_imm` (Família 6) com custo total 1, emitindo diretamente `addi v1, v0, 5`.

#### Execução (`python runner.py examples/selecao.mc --run`):
```text
12
```

---

### 2. Curto-Circuito e Efeitos Colaterais (`examples/curto_circuito.mc`)

Este programa atesta que chamadas com efeito colateral não são executadas quando o resultado lógico já estiver determinado:

```c
bool marca() {
    print("M");
    return true;
}

int main() {
    int a = 3;
    int b = 2;
    if (a < b && marca()) {
        print("ramo verdadeiro");
    }
    bool x = a < b || marca();
    print(x);
    return 0;
}
```

#### Saída da IR (`python runner.py examples/curto_circuito.mc --dump-ir`):
```text
.strings
str0: "M"
str1: "\n"
str2: "ramo verdadeiro"

marca:
  print_string str0
  print_string str1
  li v0, 1
  return v0
main:
  li v0, 3
  li v1, 2
  blt v0, v1, L0
  j L1
L0:
  call v2, marca, []
  bnez v2, L2
  j L1
L2:
  print_string str2
  print_string str1
  j L3
L1:
  j L3
L3:
  blt v0, v1, L4
  j L5
L5:
  call v3, marca, []
  bnez v3, L4
  j L6
L4:
  li v4, 1
  j L7
L6:
  li v4, 0
L7:
  print_bool v4
  print_string str1
  li v5, 0
  return v5
```

#### Execução (`python runner.py examples/curto_circuito.mc --run`):
```text
M
true
```

> **Comportamento Verificado**:
> 1. No `if (a < b && marca())`: como `3 < 2` é falso, a função `marca()` **não** é chamada.
> 2. Em `bool x = a < b || marca()`: como `3 < 2` é falso, o lado direito é obrigatoriamente avaliado, imprimindo `"M"` e atribuindo `true` a `x`.

---

### 3. Fluxo Integrado e Potência de Dois (`examples/integrado.mc`)

Combina repetição com `while`, seleção de deslocamento aritmético para multiplicação por potência de 2 (`* 8` $\to$ `slli 3`) e curto-circuito com literal:

```c
bool marca() { print("chamada"); return true; }
int main() { int x=0; while (x<3) { print(x*8); x=x+1; } bool b=true || marca(); print(b); return x; }
```

#### Saída da IR (`python runner.py examples/integrado.mc --dump-ir`):
```text
.strings
str0: "chamada"
str1: "\n"

marca:
  print_string str0
  print_string str1
  li v0, 1
  return v0
main:
  li v0, 0
L0:
  li v1, 3
  blt v0, v1, L1
  j L2
L1:
  slli v2, v0, 3
  print_int v2
  print_string str1
  addi v3, v0, 1
  mv v0, v3
  j L0
L2:
  j L3
L3:
  li v4, 1
  j L5
L4:
  li v4, 0
L5:
  print_bool v4
  print_string str1
  return v0
```

#### Execução (`python runner.py examples/integrado.mc --run`):
```text
0
8
16
true
```

> **Destaques**:
> - `x * 8` é reconhecido pela regra `mul_reg_pow2` (Família 8) como potência de dois ($8 = 2^3$), emitindo `slli v2, v0, 3` a custo 1.
> - `x = x + 1` seleciona `add_reg_imm` e emite `addi v3, v0, 1`.
> - `true || marca()` salta diretamente para o ramo de materialização `true`, sem chamar `marca()`.

---

## Suíte de Testes e Validação

A validação do projeto é automatizada via `pytest` e cobre 87 testes públicos distribuídos em três arquivos:

```sh
# 1. Testes de infraestrutura básica (IR, interpretador e limites)
python -m pytest -q tests/test_infrastructure.py

# 2. Testes de expressões e curto-circuito inicial
python -m pytest -q tests/test_codegen.py

# 3. Cenários públicos ampliados (87 testes completos)
python -m pytest -q tests/test_public_scenarios.py

# Suíte pública completa
python -m pytest -q
```

Também é possível gerar o relatório estruturado em formato JSON através de `run_tests.py`:
```sh
python run_tests.py --report test-results.json
```

### Resultado da Suíte de Testes:
```text
........................................................................ [ 82%]
...............                                                          [100%]
87 passed in 0.23s
```

Todos os **87 testes públicos passam integralmente com 100% de sucesso**.

---

## Checklist de Conclusão e Entrega

- [x] **Frontend Preservado em `previous/`**: lexer, parser, tabelas de símbolos, resolução de nomes, verificação de tipos e análises de fluxo integrados sem alterações nas interfaces originais.
- [x] **Catálogo Normativo Fechado (`catalogue.py`)**: 20 famílias normativas implementadas com seus custos normativos e predicados de imediato (`imm12`, `neg_imm12`, `pow2`).
- [x] **Seletor de Instruções com DP (`selector.py`)**: percurso pós-ordem com memorização em `SelectionTable`, seleção de custo mínimo por classe de resultado e suporte a listas de argumentos com `Args`.
- [x] **Gerador de Código Completo (`codegen.py`)**:
  - [x] Tradução de funções, blocos, declarações locais e atribuições com identificadores mapeados por identidade de símbolo (`VReg` persistente).
  - [x] Comandos condicionais (`if`, `if/else`) e laços (`while`) com controle de fluxo estruturado por rótulos.
  - [x] Suporte completo a chamadas como comando (`CallStmt` $\to$ `EFFECT`) e em expressões com retorno (`REG` e `COND`).
  - [x] Curto-circuito estrito em `&&` e `||` sem avaliação prematura de operandos com efeito colateral.
  - [x] Materialização de expressões booleanas com controle diamante (`and_reg`, `or_reg`).
  - [x] String pool centralizado com emissão de quebras de linha (`\n`) para cada comando `print`.
  - [x] Emissão de `Return(None)` ao final de funções `void`.
- [x] **Infraestrutura e Interpretador (`ir.py`, `executor.py`)**: validação estática de operandos, conformidade de intervalos imediatos e interpretação precisa em 64 bits.
- [x] **Execução e Suíte de Testes**: 87/87 testes públicos passando com tempo inferior a 1 segundo.
