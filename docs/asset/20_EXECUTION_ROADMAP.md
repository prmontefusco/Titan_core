# 20 — EXECUTION ROADMAP — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Sequência faseada (constituição §33, §38, §46). Cada passo: 1 PR, escopo mínimo, revisável numa sessão
(constituição §35). Nenhum passo de Asset (`A*`) altera `packages/core_*` — se precisar, vira PR de Shared
Integration próprio com `CORE_CHANGE_REQUEST` e ADR se mudar contrato.

Fluxo canônico do Titan (`AGENTS.md`): `IDEA → DISCOVERY → DECISION → SPEC → PLAN → BUILD → VERIFY → ACCEPT`.
Este roadmap cobre de DECISION a ACCEPT do primeiro slice.

---

## 1. Pré‑requisitos (não são Asset — Shared Integration / decisão)

| # | Item | Lane | Estado |
|---|---|---|---|
| P0 | Mergear a stack `integration/core/parallel-vertical-foundation` (G1–G3, S‑M1–S‑M3) | Shared Integration | pronta; aguarda revisão do dono |
| P1 | Aceitar decisões **A** (migrations D→C), **F** (cadeia de integridade F1 + teste), **G** (OM/Site — G1 como padrão). **B** fica para A1. | Dono | pendente |
| P2 | Teste de concorrência da cadeia de integridade (decisão F): `append` simultâneo de dois módulos para a mesma Organization, sem deadlock nem hash órfão | Shared Integration | pendente |
| P3 | `apps/api/_registry.py` iterado por `main.py` **sem mover** os routers de Livestock (aditivo) | Shared Integration | pendente (pré‑req de A5) |
| P4 | `apps/worker/dispatch.py` despacho real keyed por `message_type` (só se o slice tiver mensagem assíncrona — B2) | Shared Integration | condicional |
| P5 | Criar worktree `Titan-asset/` em `vertical/asset/*` (decisão C) | Asset | ao iniciar A2 |

## 2. Discovery — estado

| Doc | Estado |
|---|---|
| 01 Vision · 02 Domain Discovery · 03 Ubiquitous Language · 04 Bounded Context Map | ✅ |
| 05 Domain Model · 06 Aggregate Analysis · 07 Invariants | ✅ |
| 08 Domain Events · 09 Command Model | ✅ |
| 11 Authorization Model (resolve decisão G) | ✅ |
| 19 Risk Register · 20 Execution Roadmap | ✅ |
| 10 Temporal · 12 Audit · 13 Integration · 14 3D · 15 SLI Contract (detalhe) · 16 Inventory (detalhe) · 17 Maintenance (detalhe) · 18 UX Operating Model | **diferidos** — §4 |
| `MULTI_AGENT_ARCHITECTURE_REVIEW.md` (§49) | pendente — após revisão adversarial (Claude) e de integração (Gemini) deste conjunto |

**Recomendação de Discovery:** `PROCEED` para o slice, condicionado a P1.

## 3. Trilha Asset — o primeiro slice

Slice‑alvo (constituição §46, §47): **Vehicle + Part + Configuration + StockLocation + Inventory +
SLI Contract + Work Order + Material Reservation + Workshop Dashboard**, cobrindo os cenários **A** e **B**
ponta a ponta e exercendo **C/D/E** por teste.

| Passo | Conteúdo | Pré‑req | Critério de aceite (constituição §37) |
|---|---|---|---|
| **A1** | ADR do slice: decide **B** (`sustainment` mesma vertical / irmã) a partir dos invariantes; fixa a máquina de estados da `WorkOrder`; fixa G1/G2; SPEC do slice com os 16 pontos do §47 como critérios | P1, Discovery | ADR aceita; sem BLOQUEADOR de Claude; máquina de estados com todas as transições especificadas (`05` §3) |
| **A2** | `packages/asset_domain` — só entidades/VOs/eventos do slice (`05` §1). Testes de invariante I‑VEH/CFG/PRT/APP/INV (domínio) | A1, P0 | invariantes com teste; `grep livestock` vazio em `packages/asset_*`; `tests/architecture` verde varrendo `asset` |
| **A3** | `packages/asset_infrastructure/persistence` — tabelas do slice (schema `core_audit`, FK composta por Organization, RLS, carimbo `titan.module_owner=asset`) + **A‑M1**: `env.py` próprio de Asset com `make_include_object(owned_tokens={"asset"}, fk_allowlist={("core_identity","organizations")})`, *branch label* `asset`, 1ª revisão `depends_on` → revisão do Core que cria `organizations` | A2, P0 (S‑M1–S‑M3) | `alembic upgrade heads` do zero cria o schema completo; `alembic check` com o `env.py` de Asset → "no changes"; `pg_dump` do schema de Livestock inalterado; RLS provada sob role restrita |
| **A4** | `packages/asset_application` — serviços dos comandos de `09`. `authorization.py` (permissões de `11` §3) e `AssetOperationContext` (`site_scope`, `11` §2). **`sustainment_*`** (ou o namespace decidido em A1) para `SLIContract`, `Entitlement` via `Evaluation→Decision` do Core, `WorkOrder` workflow, `WorkshopDashboard` projeção | A2, A3 | I‑SLI‑1..5 e I‑WO‑1..5 com teste; entitlement tem `decision_ref` (não `if`); disputa de estoque (cenário C) produz `Decision`; concorrência de estoque provada contra Postgres real |
| **A5** | `apps/api/asset/` — routers + `dependencies.py` (espelha `livestock_dependencies.py`: HTTP→OIDC→OrganizationContext→AssetOperationContext→Permission→Service→transação→RLS→repo), registrado no `_registry.py` | A4, P3 | contrato OpenAPI aditivo (subconjunto de Livestock inalterado — `SHARED_CHANGE_PROTOCOL.md` §7); testes de contrato de API; 401/403 declarados |
| **A6** | Workshop Dashboard e Fleet View como projeções de leitura + repositórios de leitura; recalculador de `WAITING_MATERIAL` e de `PriorityScore` por evento | A4 | dashboard responde "o que fazer a seguir" com breakdown de prioridade e o que bloqueia (I‑WO‑4/5); Fleet View por estado |
| **A7** | Suíte de integração ponta a ponta dos cenários **A** e **B**; testes de invariante para **C/D/E**; roteiro executável em `apps/validacao/asset/` | A5, A6 | os **16 pontos do §47** respondidos com evidência num teste ponta a ponta; `TITAN_REQUIRE_INTEGRATION_DB=1 pytest` verde; gate completo (`ruff`/`ruff format`/`mypy`/`alembic check`) verde |

Cada `A*` é um PR na branch `vertical/asset/*`; nenhum toca `core_*`; `docs/CHECKLIST_DE_IMPLEMENTACAO.md`
recebe a entrada do passo no mesmo commit (`AGENTS.md`).

## 4. Documentos de discovery diferidos (não bloqueiam A1)

| Doc | Por que pode esperar | Quando |
|---|---|---|
| 10 Temporal Model | O slice usa `shared_kernel.temporal` e o padrão ADR‑0061 do Core; os pontos temporais estão em `07` (I‑VEH‑2, I‑SLI‑1/2) | antes de A4 |
| 12 Audit Model | Reusa `event_log` + cadeia de integridade + `checkpoint` do Core; pontos em `07` (I‑WO‑3) e `08` §4 | antes de A4 |
| 13 Integration Model (ERP/PLM/WMS) | Fora do slice (constituição §14); a demanda de material **para** em "falta detectada" | antes do 2º slice |
| 14 3D Technical Asset Model | Só fronteira/adapter no slice (constituição §9, §10) | antes do slice de catálogo |
| 15/16/17 SLI/Inventory/Maintenance (detalhe) | O essencial está em `05`/`06`/`07`; detalhamento é refino | durante A1/A4 conforme necessário |
| 18 UX Operating Model | Backend do slice entrega as queries de `09` §3; o frontend tem plano próprio (AR‑13) | em paralelo a A5/A6 |

## 5. Marcos e revisões (constituição §33, §49)

```
DISCOVERY (01-09,11,19,20) ──▶ REVISÃO ADVERSARIAL (Claude) ──▶ REVISÃO DE INTEGRAÇÃO (Gemini)
        │                                                              │
        └──────────────▶ MULTI_AGENT_ARCHITECTURE_REVIEW.md ◀──────────┘
                                    │
                          DONO: ACCEPT do slice + decisões A/F/G
                                    │
                              A1 (ADR + SPEC) ──▶ A2..A7 ──▶ VERIFY ──▶ ACCEPT do slice
```

**Antes de recomendar implementação, os três agentes respondem (constituição §49):**
- Codex: "Esta arquitetura pode ser implementada incrementalmente sem quebrar Titan?"
- Claude: "Que premissas podem fazer esta arquitetura falhar em produção?"
- Gemini: "Um técnico/planejador/logístico/gestor de contrato real completa o fluxo ponta a ponta sem
  navegar a arquitetura?"

## 6. Primeiro milestone (constituição §47) — critério de pronto

O teste ponta a ponta de A7 deve, para um veículo sob contrato SLI com necessidade de manutenção,
responder **com evidência para cada resposta**: (1) qual veículo, (2) qual configuração, (3) qual OM,
(4) qual contrato, (5) qual versão, (6) que ação, (7) qual peça, (8) aplicável?, (9) onde existe,
(10) quanto disponível, (11) pode reservar?, (12) o que bloqueia, (13) qual SLA, (14) o que a oficina faz
a seguir, (15) por que priorizada, (16) que evidência sustenta cada resposta.

Se a arquitetura não responde isso de forma limpa, **não está pronta** (constituição §47).
