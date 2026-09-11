# 19 — RISK REGISTER — Titan Asset & Sustainment

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset. Vivo — revisar a cada slice.
Severidade conforme constituição §31: **BLOQUEADOR / HIGH / MEDIUM / LOW / OBSERVAÇÃO**.
Fonte dos itens herdados: `docs/architecture/PHASE0_ADVERSARIAL_REVIEW.md` e
`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`.

---

## 1. Riscos herdados da Fase 0 (arquitetura / paralelismo)

| ID | Sev. | Risco | Estado / mitigação |
|---|---|---|---|
| **B1** | BLOQUEADOR | "Ambiente de migrations por vertical" quebra `alembic check`/`upgrade head` sem `include_object` por dono e sem `head→heads` | **Endereçado**: `MIGRATION_CONCURRENCY_STRATEGY.md` (Opção D→C); S‑M1–S‑M3 implementados na branch `integration/core/parallel-vertical-foundation`. **Bloqueia A3** (migrations de Asset) até merge de S‑M1–S‑M3 + **A‑M1** (`env.py` de Asset usando `make_include_object`). Não bloqueia A1/A2. |
| **H1** | HIGH | Cadeia de integridade de eventos é por Organization; duas verticais no mesmo tenant interleavam e serializam `append` | Classificado como **garantia global do Core** (decisão F, recomendação F1). **Exige teste de concorrência antes do primeiro slice** (`ThreadPoolExecutor`+`Barrier`, dois módulos, mesma Organization). Nenhum código de Asset toca integridade. |
| **H2** | HIGH | RLS por Organization não isola OM/Site; `OrganizationContext` do Core insuficiente para atores restritos a site | **Endereçado**: `11_AUTHORIZATION_MODEL.md` — decisão G1 (escopo de site na vertical, nada no Core). A1 escolhe G1 vs G2 por cliente. CCR só se G1 se mostrar insuficiente. |
| **H3** | HIGH | Os 6 docs de assessment não são o entregável §48; faltavam 01–20 e `MULTI_AGENT_ARCHITECTURE_REVIEW.md` | **Em andamento**: 01–09, 11, 19, 20 produzidos neste bloco. Faltam 10, 12–18 (diferidos, não bloqueiam A1 — ver `20_EXECUTION_ROADMAP.md` §4) e `MULTI_AGENT_ARCHITECTURE_REVIEW.md` (§49 — após revisão de Claude e Gemini). |
| M1 | MEDIUM | `require_existing_root` fica vermelho ao registrar `asset` no manifesto | **Resolvido** em G2 da stack: contrato novo da guarda (pula vertical registrada sem pacote se `status` bootstrap; falha se nenhuma foi varrida). |
| M2 | MEDIUM | Teste vertical⊥vertical depende da decisão B (não decidida) | **Contornado**: Passo 1 registra só `("livestock","asset")`; `sustainment` fora até a ADR do slice (A1). |
| M3 | MEDIUM | "Nenhuma transação cruza duas verticais" sem enforcement | Endereçado no desenho: `MULTI_VERTICAL_CI_GATES.md` §8 (transaction boundary gate, G7). No slice, a única operação inter‑módulo é `ReserveMaterialForWorkOrder` (B1: mesma vertical). |
| M4 | MEDIUM | ADR‑0080 sem seções §30 de Segurança/Auditoria | **Resolvido**: reconciliação adicionada à ADR‑0080. |

## 2. Riscos de domínio do primeiro slice (novos)

| ID | Sev. | Risco | Cenário de falha | Mitigação | Teste de regressão |
|---|---|---|---|---|---|
| **AR‑01** | HIGH | **Disponibilidade** modelada como número, não rede: `available` vira campo/boolean armazenado | "peça disponível = true" some com o motivo; disputa produção×SLI×venda não explicável (cenário C) | `available` **sempre** calculado on‑read com `AvailabilityBreakdown`; disputa → `Decision` do Core (I‑INV‑1/2) | I‑INV‑1/2; cenário C ponta a ponta com 3 demandas e `decision_ref` |
| **AR‑02** | HIGH | **Contexto contratual** não congelado na WO: reavaliação com a versão de hoje | contrato emenda durante WO aberta; faturamento/entitlement usa versão errada (cenário E) | `ContractContext` VO imutável, resolvido por seleção temporal (I‑SLI‑1/2) **antes** de qualquer regra; anexado a cada evento | cenário E: WO sob versão A, emenda para B, dossiê cita A nos eventos anteriores |
| **AR‑03** | HIGH | **Entitlement como `if`** em `work_order_service` em vez de `Evaluation→Decision` governada | lógica de cobertura duplicada, não auditável, diverge da governança do Core; IA vira fato (constituição §23) | `SUSTAINMENT_ENTITLEMENT.RESOLVE` delega ao Core; `grep` não acha regra de cobertura fora de `Rule`/`Evaluation` (I‑SLI‑4) | I‑SLI‑4/5; teste de que o entitlement retornado tem `decision_ref` com breakdown |
| **AR‑04** | HIGH | **Aplicabilidade booleana**: `is_compatible: true` sem evidência | frontend/planejamento instala peça incompatível; catálogo 3D "decide" aplicabilidade (cenário F) | `Applicability` = agregado com `evidence_ref` obrigatório; consulta retorna asserção+evidência (I‑APP‑1) | I‑APP‑1; consulta de aplicabilidade nunca retorna só `true` |
| **AR‑05** | HIGH | **Perda de inventário** em transferências/reservas concorrentes | duas reservas simultâneas somando > `on_hand`; transferência + reserva concorrentes contam a mesma unidade duas vezes | `version` por `StockPosition` + `SELECT ... FOR UPDATE` das posições afetadas antes de calcular/gravar (I‑INV‑3/4) | I‑INV‑1/3/4 com `ThreadPoolExecutor`+`Barrier` contra Postgres real |
| **AR‑06** | MEDIUM | **Supersessão apaga história**: baseline as‑maintained histórica passa a apontar a revisão nova (cenário D) | auditoria contratual e confiabilidade perdem "o que estava instalado quando" | supersessão é evento aditivo; instalações append‑only; planejamento novo usa a substituta **se aplicável** (I‑PRT‑1, I‑APP‑2) | cenário D: superseder 2→3; baseline de 2026‑01 ainda mostra rev. 2 |
| **AR‑07** | MEDIUM | **Máquina de estados da WO** copiada de Maximo ou virando strings sem transições | estado muda sem evento/auditoria; `WAITING_MATERIAL` decorativo (constituição §42) | máquina derivada do domínio (`05` §3); toda transição = evento + auditoria + motivo quando exigido; `WAITING_MATERIAL` derivado (I‑WO‑3/4) | I‑WO‑3/4; cada transição gera exatamente um evento |
| **AR‑08** | MEDIUM | **`WorkOrder` vira God Aggregate** absorvendo contrato, veículo, estoque | acoplamento de 3 bounded contexts; agregado gigante | WO congela `ContractContext` VO e referencia `Vehicle`/`StockReservation` por id; reserva é agregado próprio (`06` §3) | teste de fronteira: `WorkOrder` não importa repositório de `SLIContract`/`StockPosition` |
| **AR‑09** | MEDIUM | **`site_scope` aplicado tarde** — depois de resolver o dado | vazamento de OM não autorizada antes do filtro (H2 residual) | autorização + escopo **antes** do `SELECT` de negócio; recurso fora do escopo → `404` (I‑SEC‑2) | teste "escopo antes da resolução" (`11` §6) |
| **AR‑10** | MEDIUM | **Prioridade não determinística/explicável** ou score oculto | UI não explica por que WO‑1 vem antes de WO‑2; tentação de IA (constituição §22) | `PriorityScore` = função pura de fatores+pesos de `Rule` versionada; breakdown + `evaluation_ref` na resposta (I‑WO‑5) | I‑WO‑5: mesma entrada → mesmo score; mudar peso exige nova versão da Rule |
| **AR‑11** | LOW | **Notificação** nasce em `sustainment_application` e vira capacidade horizontal no lugar errado | duplicação quando a 2ª vertical precisar; anti‑padrão MISPLACED | pré‑registrado: nasce como projeção+outbox na vertical; candidata a Core quando a 2ª consumidora aparecer — não extrair antes (`04` §5) | — |
| **AR‑12** | LOW | **Adapter de ERP/PLM/WMS** reinventado ou extraído cedo demais | duas verticais com andaime de adapter semelhante | contrato de integração é propriedade da vertical; **fora do slice**; não extrair antes de uso comprovado nas duas (`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §3) | — |
| **AR‑13** | OBSERVAÇÃO | **`apps/web` de Asset** sem plano | dashboard de oficina (parte do slice‑alvo) sem frontend | `18_UX_OPERATING_MODEL.md` (pendente) + árvore de rotas própria ou app separado; o backend do slice entrega as queries de `09` §3 | — |
| **AR‑14** | OBSERVAÇÃO | **`titan.module_owner` inconsistente** (`livestock` vs `titan_livestock`) — pode contaminar o padrão de Asset | filtro de migrations frágil | Asset usa **um** token (`asset`); manifesto documenta; padronização de Livestock é PR de lane Livestock separado | teste `test_vertical_manifest` (owners/aliases disjuntos) |
| **AR‑15** | OBSERVAÇÃO | **3D / catálogo interativo / AR** acoplado ao domínio de manutenção | reescrita futura quando o catálogo 3D chegar | só fronteira/adapter no slice (constituição §9, §10); `14_3D_TECHNICAL_ASSET_MODEL.md` diferido | — |

## 3. Riscos de processo

| ID | Sev. | Risco | Mitigação |
|---|---|---|---|
| PR‑01 | MEDIUM | Trabalho de Asset produz *diff* em arquivo que o Codex edita (Livestock) | `PARALLEL_VERTICAL_SAFETY` + File Ownership Guard + worktree `Titan-asset/` em `vertical/asset/*` |
| PR‑02 | MEDIUM | `_registry.py` / `dispatch.py` (Shared Integration) viram gargalo entre lanes | são PRs aditivos pequenos, serializados; não movem routers de Livestock (janela de integração) |
| PR‑03 | LOW | Commit base `f6cc85b` da stack Lane C mistura `docs/asset/` (Lane B) | ao fatiar em PRs reais, `docs/asset/` sai de `f6cc85b`; esta branch `vertical/asset/discovery` é a origem correta |
| PR‑04 | MEDIUM | ADR do slice (A1) e teste vertical⊥vertical (Passo 1) têm dependência circular via decisão B | A1 **precede** o registro de `sustainment` no manifesto; Passo 1 fica com `("livestock","asset")` |

## 4. Itens que exigiam decisão do dono antes de A2 (código) — todas ACEITAS em 10–11/09/2026

- **Decisão A** (migrations D→C) — ✅ aceita, executada (S‑M1–S‑M3).
- **Decisão B** (`sustainment` = mesma vertical, B1) — ✅ aceita na ADR de A1.
- **Decisão F** (escopo da cadeia de integridade) — ✅ resolvida: é por agregado, confirmado por teste real (P2).
- **Decisão G** (OM/Site) — ✅ aceita: G1 modelado e aprovado para o slice.
- **Decisão C** (worktrees/branch por lane) — ✅ já aceita; branch por lane em uso.

Restam apenas itens de execução (P0 merge, P3 `_registry.py`), não decisões.
