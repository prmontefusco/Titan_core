# DECISIONS_REQUIRED_PHASE0 — Decisões abertas antes de implementar Titan Asset

**Status:** Proposta para revisão. Decisões pendentes do dono (constituição §32, §34).
**Data:** 10 de setembro de 2026
**Formato:** constituição §34. Posições de Codex e Gemini marcadas "não consultado nesta sessão" — não
fabricar consenso.

---

## DECISÃO A — Estratégia de concorrência de migrations — **ACEITA, 10/09/2026**

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
**Owner decision required: YES — ACEITA.** Executada em S‑M1–S‑M3 (`integration/core/parallel-vertical-foundation`);
A‑M1 (env.py de Asset no modelo C) segue como próximo passo da trilha Asset.

---

## DECISÃO B — `sustainment` é o mesmo `vertical_id` de `asset` ou vertical irmã isolada? — **ACEITA (B1), 11/09/2026**

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
**Confiança: MÉDIA.** **Owner decision required: YES — ACEITA** via aprovação de
`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` (11/09/2026, Status ACEITA).
`sustainment` segue **não registrado** em `verticals.toml` (correto sob B1 — evento sob o namespace
`asset.sustainment.*`, sem `vertical_id` próprio); atualizar o manifesto é Shared Integration referenciando
essa ADR.

---

## DECISÃO C — Layout de worktree/branch e obrigatoriedade — **ACEITA, 10/09/2026**

**Questão.** Tornar o layout multi‑worktree de [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md)
obrigatório para trabalho concorrente de verticais?

| Opção | Vantagens | Riscos |
|---|---|---|
| **C1** — worktrees obrigatórios (`Titan-livestock/`, `Titan-asset/`, `Titan-core-integration/`) + prefixo de branch como fonte de lane | elimina edição concorrente da mesma árvore; prefixo alimenta o File Ownership Guard | disciplina operacional nova; setup por agente |
| **C2** — um checkout, coordenação por "um agente por arquivo" (AGENTS.md atual) | zero setup | não escala a duas verticais grandes editando em paralelo; colisão provável |

**Posições.** Claude: **C1**. Codex/Gemini: não consultados.

**Recomendação.** **C1**. **Confiança: ALTA.** **Owner decision required: YES — ACEITA.** Aplicada como
política: branch por lane é obrigatório (`vertical/asset/discovery`, `integration/core/parallel-vertical-foundation`
já em uso, nunca commit direto na lane errada). O worktree físico separado (`Titan-asset/`,
`Titan-core-integration/`) fica reservado para quando houver concorrência real entre agentes no mesmo
checkout — nesta sessão, um agente por vez, a troca de branch no mesmo checkout mais o protocolo de
pré‑edição (`AGENT_WORKTREE_SAFETY.md` §4) já cumprem a garantia de não misturar lanes.

---

## DECISÃO D — Alocação de número de ADR sob agentes concorrentes

**Questão.** Evitar que dois agentes gravem `0081` independentemente.

| Opção | Vantagens | Riscos |
|---|---|---|
| **D1** — rascunho `draft-<data>-<slug>.md` sem número; número alocado só na integração pelo integrador | à prova de colisão; não reescreve histórico | exige o passo de renomear na integração |
| **D2** — reservar faixas por lane (ex.: Asset usa 0100+) | simples | desperdiça faixa; ainda colide dentro da lane; polui a numeração |

**Posições.** Claude: **D1** (detalhe em [`AGENT_WORKTREE_SAFETY.md`](AGENT_WORKTREE_SAFETY.md) §7). Codex/
Gemini: não consultados.

**Recomendação.** **D1**. **Confiança: ALTA.** **Owner decision required: YES** — não houve ACCEPT explícito
separado, mas D1 está **em uso de fato** desde G1 sem objeção (as duas ADRs desta stack usam
`draft-<data>-<slug>.md` sem número). Falta o registro formal em `docs/adr/README.md` — Shared Integration
pendente, não bloqueia execução.

---

## DECISÃO E — Registro/manifesto de verticais

**Questão.** Introduzir `docs/architecture/verticals.toml` como fonte da verdade de composição?

| Opção | Vantagens | Riscos |
|---|---|---|
| **E1** — manifesto explícito lido por `tests/architecture` + CI; sem comportamento de domínio; Core não o importa | lista única; teste genérico; onboarding da Nª vertical não reescreve teste | mais um arquivo de configuração para manter em dia |
| **E2** — manter listas *hard‑coded* em cada teste/portão | nada novo | duplicação; toda vertical nova edita vários arquivos; risco de divergência |

**Posições.** Claude: **E1**, implementado no G1 de [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md).
Codex/Gemini: não consultados.

**Recomendação.** **E1**. **Confiança: MÉDIA‑ALTA.** **Owner decision required: YES** — não houve ACCEPT
explícito separado, mas E1 está **implementada e em uso** desde G1
(`docs/architecture/verticals.toml`, consumido por `tests/architecture/` e `scripts/check_file_ownership.py`).

---

## DECISÃO F — Escopo da cadeia de integridade de eventos (HIGH H1) — **RESOLVIDA, 11/09/2026**

**Questão original.** A finding H1 partiu de uma leitura parcial de `events.py` (só as linhas do trecho
grepado) e concluiu que a cadeia de `event_integrity_table` é filtrada só por
`record_owner_organization_id`, logo verticais diferentes interleavam e serializam entre si numa mesma
cadeia. **Essa premissa estava errada.**

**O que o código realmente faz** (`DomainEventRepository.append`, `events.py`): o `pg_advisory_xact_lock` é
adquirido numa chave `f"{organization_id}:{aggregate_type}:{aggregate_id}"`, e a busca de `current_version`/
`previous_hash` filtra por `(record_owner_organization_id, aggregate_type, aggregate_id[, aggregate_version])`
— **a cadeia é por agregado**, não uma cadeia global por Organization. `WorkOrder` (Asset) e `Animal`
(Livestock) na mesma Organization usam chaves de lock diferentes; não há disputa nem interleaving entre eles.

| Opção | Avaliação |
|---|---|
| **F1** — declarar que a cadeia é **garantia do Core por agregado** (não por Organization); confirmar por teste de concorrência real | **É o que o código já faz.** Nenhuma mudança de Core necessária. |
| ~~F2 — reescopar a cadeia~~ | **Descartada** — não há o problema que resolveria. |

**Evidência de fechamento:** `tests/integration/test_domain_events_postgresql.py` ganhou dois testes com
conexões/transações reais por thread (`ThreadPoolExecutor`+`Barrier`, sem mock):
`test_concurrent_appends_to_the_same_aggregate_serialize_via_advisory_lock` (mesmo agregado — serialização
correta preservada) e `test_concurrent_appends_to_different_aggregates_do_not_serialize` (agregados
diferentes, mesma Organization — thread B termina/comita antes de thread A apesar de A segurar a transação
aberta; prova ausência de espera cruzada). Ambos verdes, estáveis em execuções repetidas.

**Decisão:** **F1‑confirmado‑por‑teste.** Nenhum código de Asset toca integridade; os dois testes entram no
Nível 2 de CI (`MULTI_VERTICAL_CI_GATES.md`) como regressão permanente — se algum dia a busca de
`previous_hash`/o lock forem re‑escopados só por Organization, esses testes quebram primeiro.
**Confiança: ALTA** (empírica, não só leitura de código). **Owner decision required:** NÃO — a decisão é
factual (o design já é o que F1 pedia), registrada aqui para o rastro de auditoria da revisão.

---

## DECISÃO G — Autorização OM/Site (HIGH H2) — **ACEITA (G1), 11/09/2026**

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

**Fechamento (11/09/2026).** A discovery de domínio (`docs/asset/11_AUTHORIZATION_MODEL.md`) modelou os
cenários reais de acesso e concluiu por um **G1 concreto para o 1º slice**: `CustomerSite` como entidade de
`asset_domain`; `AssetOperationContext` estende o `OrganizationContext` do Core com `site_scope`; predicado
de escopo aplicado **antes** da resolução do dado (I‑SEC‑2); RLS por Organization como barreira dura;
nenhum conceito `OM`/`Vehicle`/`Workshop`/`CustomerSite` no Core. Aprovado via
`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` (Status ACEITA). **G2** (OM como
Organization própria) permanece registrada como opção para quando houver cliente com OM independente — não
é o caso do 1º slice; ADR de continuação decide se e quando.

---

## Resumo

| Decisão | Status | Confiança | Bloqueia início de Asset? |
|---|---|---|---|
| A — migrations | **ACEITA** 10/09 — D→C executada (S‑M1–S‑M3) | ALTA | A‑M1 (env.py de Asset) ainda pendente |
| B — `sustainment` | **ACEITA** 11/09 — B1, na ADR do slice | MÉDIA | Não — resolvida |
| C — worktree/branch | **ACEITA** 10/09 — C1 (branch por lane obrigatório) | ALTA | Não — em uso |
| D — número de ADR | Em uso de fato (D1); registro formal em `docs/adr/README.md` pendente | ALTA | Não |
| E — manifesto | Implementada (E1) | MÉDIA‑ALTA | Não |
| F — cadeia de integridade | **RESOLVIDA** 11/09 — F1 confirmado por teste real | ALTA | Não |
| G — OM/Site | **ACEITA** 11/09 — G1 modelado e aprovado para o 1º slice | ALTA | Não — resolvida |

**Restam para A2 começar:** P0 (merge desta stack), P3 (`apps/api/_registry.py`), revisão adversarial +
integração da discovery com `MULTI_AGENT_ARCHITECTURE_REVIEW.md` (§49), e A‑M1 (ambiente de migrations
próprio de Asset).
