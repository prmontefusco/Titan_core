# DECISIONS_REQUIRED_PHASE0 — Decisões abertas antes de implementar Titan Asset

**Status:** Proposta para revisão. Decisões pendentes do dono (constituição §32, §34).
**Data:** 10 de setembro de 2026
**Formato:** constituição §34. Posições de Codex e Gemini marcadas "não consultado nesta sessão" — não
fabricar consenso.

---

## DECISÃO A — Estratégia de concorrência de migrations

**Questão.** Como Livestock e Asset autoram schema concorrentemente sem serializar (restrição §9) e sem quebrar
`alembic check`/`upgrade head` (BLOQUEADOR B1)?

**Invariante relevante.** ADR‑0001 §comportamento preservado; `alembic check` limpo; instalação limpa e
upgrade produzem o mesmo schema; migration de vertical não toca tabela de outra (restrição §10).

| Opção | Vantagens | Riscos |
|---|---|---|
| **A** — grafo global único + lane de merge serializada | zero mudança de infra; tudo o que já funciona segue | serializa a autoria de schema — viola a restrição §9 |
| **B** — `version_locations` por dono + `env.py` único + `upgrade heads` | boa concorrência; pouca mudança | `env.py` único continua ponto Lane C compartilhado; troca `head→heads` repo‑wide |
| **C** — `env.py` por vertical + filtro `include_object` por `titan.module_owner` + *branch labels* + `upgrade heads` | concorrência plena; `alembic check` correto por vertical; custo constante para a Nª vertical | exige extrair o ambiente de Livestock (R1, risco ALTO) ou conviver com assimetria |
| **D** — transição: cadeia de Livestock intocada; Asset já no modelo C; camada de composição instala todas | concorrência já para o par Livestock↔Asset; risco baixo a Livestock; converge para C | assimetria temporária; troca `head→heads` ainda repo‑wide |

**Posições.** Claude: **D agora, convergir para C** numa janela de integração (detalhe em
[`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md) §4). Codex: não consultado. Gemini:
não consultado.

**Recomendação.** Opção **D → C**. **Confiança: ALTA** (evidência direta no `env.py`, `alembic.ini` e CI).
**Owner decision required: YES.**

---

## DECISÃO B — `sustainment` é o mesmo `vertical_id` de `asset` ou vertical irmã isolada?

**Questão.** `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2.1 deixa aberto; disso dependem `verticals.toml`, o teste
vertical ⊥ vertical (M2), o namespace de evento e o `migration_owner`.

**Invariante relevante.** Fronteira de bounded context deriva de invariante transacional, não de nome
(`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2).

| Opção | Vantagens | Riscos |
|---|---|---|
| **B1** — `sustainment_*` e `asset_*` são **uma** vertical (`vertical_id = asset`), podem se referenciar | permite Work Order → Vehicle/Inventory por referência direta; menos cerimônia | se Sustainment for vendável sem Asset Management, a fronteira fica errada |
| **B2** — verticais irmãs isoladas (`vertical_id = asset` e `sustainment`), colaboram só por evento/contrato | isolamento máximo; alinhado à regra vertical ⊥ vertical | *overhead* de contrato entre dois módulos que compartilham a operação "montar e reservar" |

**Posições.** Claude: **B1 como hipótese**, com gatilho explícito para B2 ("se a discovery mostrar Sustainment
vendável sem Asset Management"). Codex/Gemini: não consultados.

**Recomendação.** **B1**, decidida formalmente **na ADR do 1º slice**, a partir dos invariantes. Até lá, o
Passo 1 do bootstrap registra só `("livestock", "asset")` e adia `sustainment` por escrito.
**Confiança: MÉDIA.** **Owner decision required: YES** (na ADR do slice).

---

## DECISÃO C — Layout de worktree/branch e obrigatoriedade

**Questão.** Tornar o layout multi‑worktree de [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md)
obrigatório para trabalho concorrente de verticais?

| Opção | Vantagens | Riscos |
|---|---|---|
| **C1** — worktrees obrigatórios (`Titan-livestock/`, `Titan-asset/`, `Titan-core-integration/`) + prefixo de branch como fonte de lane | elimina edição concorrente da mesma árvore; prefixo alimenta o File Ownership Guard | disciplina operacional nova; setup por agente |
| **C2** — um checkout, coordenação por "um agente por arquivo" (AGENTS.md atual) | zero setup | não escala a duas verticais grandes editando em paralelo; colisão provável |

**Posições.** Claude: **C1**. Codex/Gemini: não consultados.

**Recomendação.** **C1**. **Confiança: ALTA.** **Owner decision required: YES.**

---

## DECISÃO D — Alocação de número de ADR sob agentes concorrentes

**Questão.** Evitar que dois agentes gravem `0081` independentemente.

| Opção | Vantagens | Riscos |
|---|---|---|
| **D1** — rascunho `draft-<data>-<slug>.md` sem número; número alocado só na integração pelo integrador | à prova de colisão; não reescreve histórico | exige o passo de renomear na integração |
| **D2** — reservar faixas por lane (ex.: Asset usa 0100+) | simples | desperdiça faixa; ainda colide dentro da lane; polui a numeração |

**Posições.** Claude: **D1** (detalhe em [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md) §7). Codex/
Gemini: não consultados.

**Recomendação.** **D1**. **Confiança: ALTA.** **Owner decision required: YES** — e registrar em
`docs/adr/README.md` (Shared Integration).

---

## DECISÃO E — Registro/manifesto de verticais

**Questão.** Introduzir `docs/architecture/verticals.toml` como fonte da verdade de composição?

| Opção | Vantagens | Riscos |
|---|---|---|
| **E1** — manifesto explícito lido por `tests/architecture` + CI; sem comportamento de domínio; Core não o importa | lista única; teste genérico; onboarding da Nª vertical não reescreve teste | mais um arquivo de configuração para manter em dia |
| **E2** — manter listas *hard‑coded* em cada teste/portão | nada novo | duplicação; toda vertical nova edita vários arquivos; risco de divergência |

**Posições.** Claude: **E1**, implementado no G1 de [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md).
Codex/Gemini: não consultados.

**Recomendação.** **E1**. **Confiança: MÉDIA‑ALTA.** **Owner decision required: YES.**

---

## DECISÃO F — Escopo da cadeia de integridade de eventos (HIGH H1)

**Questão.** A cadeia de `event_integrity_table` é filtrada só por `record_owner_organization_id`
(`events.py:247‑256`). Com duas verticais, os `append` de um mesmo tenant interleavam numa cadeia e
serializam entre si. Isso é intencional?

| Opção | Vantagens | Riscos |
|---|---|---|
| **F1** — declarar que a cadeia é **garantia global do Core por Organization**, interleave é esperado; validar concorrência | nada muda no Core; distinção clara "garantia do Core ≠ acoplamento vertical↔vertical" (restrição §17) | ponto de serialização de `append` cross‑vertical por tenant; dimensionar |
| **F2** — reescopar a cadeia para `(organization, aggregate)` ou `(organization, vertical)` | remove a serialização cross‑vertical | mudança de semântica de integridade no Core; ADR própria; risco a Livestock; migration |

**Posições.** Claude: **F1 agora** + teste de concorrência; reavaliar F2 se o dimensionamento doer. Codex/
Gemini: não consultados.

**Recomendação.** **F1**, documentada em ADR de Shared Integration (ou seção nova na ADR‑0079). **Nenhum
código de Asset toca integridade.** **Confiança: MÉDIA** (depende de confirmar a semântica completa de
`build_event_chain_entry`/`checkpoints.py`). **Owner decision required: YES.**

---

## DECISÃO G — Autorização OM/Site (HIGH H2)

**Questão.** Asset pode precisar de escopo sub‑Organization (OM/Site). O Core oferece RLS por Organization.
Decidir agora ou diferir?

| Opção | Vantagens | Riscos |
|---|---|---|
| **G1** — **diferir para a discovery de domínio**; modelar cenários reais de acesso antes de tocar o Core | não implementa primitiva antes de entender a necessidade (restrição §18; constituição §38) | fica como risco aberto no *risk register* |
| **G2** — decidir já que OM = Organization | reusa RLS atual sem mudança | pode estar errado; impacto em identidade/memberships/contratos/integridade se revertido depois |
| **G3** — decidir já criar `scope` genérico no Core | resolve cedo | primitiva especulativa; viola §38 se a necessidade não estiver provada |

**Posições.** Claude: **G1**. Codex/Gemini: não consultados.

**Recomendação.** **G1** — diferida para a discovery; se emergir necessidade, `CORE_CHANGE_REQUEST` provando
horizontalidade; nenhum conceito `OM`/`MilitaryOrganization`/`Workshop`/`Vehicle` no Core.
**Confiança: ALTA.** **Owner decision required: YES** (para registrar o diferimento como decisão consciente).

---

## Resumo

| Decisão | Recomendação | Confiança | Bloqueia início de Asset? |
|---|---|---|---|
| A — migrations | D → C | ALTA | **Sim** (para migrations de Asset); não para domínio/aplicação |
| B — `sustainment` | B1, na ADR do slice | MÉDIA | Não (adiar no Passo 1) |
| C — worktree/branch | C1 obrigatório | ALTA | Sim (para trabalho concorrente seguro) |
| D — número de ADR | D1 | ALTA | Não |
| E — manifesto | E1 | MÉDIA‑ALTA | Não |
| F — cadeia de integridade | F1 + teste | MÉDIA | Não (mas resolver antes do 1º slice) |
| G — OM/Site | G1 diferir | ALTA | Não |
