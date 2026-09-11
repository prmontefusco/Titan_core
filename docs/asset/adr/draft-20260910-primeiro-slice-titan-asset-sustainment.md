# ADR (RASCUNHO) — Primeiro slice de Titan Asset & Sustainment: corte de vertical, módulos, máquina de estados da Work Order e escopo de site

**Número:** a alocar na integração (política D1 de `docs/architecture/AGENT_WORKTREE_SAFETY.md` §7).
Não assumir número; o arquivo permanece com o nome `draft-...` até lá.
**Data:** 10/09/2026
**Status:** ACEITA — aprovada pelo dono em 11/09/2026. A decisão em si (B1, máquina de estados da
`WorkOrder`, G1 para o slice, layout de módulos, entitlement via `Evaluation → Decision`) é vinculante.
Execução (A2 em diante) segue gated pelos itens em aberto de "Critérios de aceitação" — aceitar a ADR não
os dispensa.
**Estado operacional no MVP:** FUTURA_APROVADA (nenhum código; decisão de estrutura do primeiro slice)
**Lane:** Asset (`vertical/asset/*`).
**Decisão de Discovery:** `PROCEED` (ver `docs/asset/20_EXECUTION_ROADMAP.md` §2), **condicionada**
às decisões A, F, G de `docs/architecture/DECISIONS_REQUIRED_PHASE0.md`.
**Complementa:** ADR‑0080 e o rascunho `draft-20260910-governanca-de-desenvolvimento-paralelo-de-verticais.md`
(estrutura de repositório e paralelismo). **Não** os substitui.
**Documentos de apoio (fonte do detalhe):** `docs/asset/01`…`09`, `11`, `19`, `20`.

---

## Contexto

A discovery do primeiro slice (Vehicle + Part + Configuration + Inventory + SLI Contract + Work Order +
Material Reservation + Workshop Dashboard) está concluída nos documentos numerados 01–09/11/19/20. Antes de
`packages/asset_*` nascer (passo A2 do roadmap), quatro decisões precisam ser fixadas por escrito, porque
determinam fronteiras de pacote e de teste que são caras de mudar depois:

1. `sustainment` é a **mesma vertical** de `asset` (podem se referenciar) ou **vertical irmã** isolada?
   (decisão **B** — pendente desde `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2.1)
2. Qual é a **máquina de estados da `WorkOrder`** (candidata em `05_DOMAIN_MODEL.md` §3, a derivar — §16 da
   constituição)?
3. Qual **modelo de autorização OM/Site** o slice adota (decisão **G** — `11_AUTHORIZATION_MODEL.md`)?
4. Qual o **layout de módulos e migrations** do slice?

---

## Decisão

### 1. Corte de vertical — **B1: uma vertical (`vertical_id = asset`), dois pacotes internos**

`packages/asset_*` e `packages/sustainment_*` formam **uma única vertical** do ponto de vista das regras de
dependência (`docs/architecture/DEPENDENCY_RULES.md`). `sustainment_application` **pode** importar a
superfície pública de `asset_application` (relação Customer/Supplier — `04_BOUNDED_CONTEXT_MAP.md` §4). A
fronteira externa verificada por CI continua sendo **`asset` ⊥ `livestock`** (nunca `sustainment` importa
`livestock`, nem vice‑versa).

**Justificativa a partir dos invariantes:** o cenário A (`09_COMMAND_MODEL.md` `ReserveMaterialForWorkOrder`)
precisa manter, **atomicamente**, I‑WO‑2 (`Σ reservado ≤ demandado` na `WorkOrder`, dono `sustainment`) e
I‑INV‑1 (`available ≥ 0` na `StockPosition`, dono `asset`). Uma saga por evento (B2) abriria uma janela em
que `reservado ≠ demandado` sem falha observável — enfraquece o invariante. Manter os dois pacotes na mesma
vertical permite a transação única quando o estoque é local, e mantém a fronteira limpa por **referência**
(`WorkOrder` aponta `StockReservation` por id) no cenário B (transferência).

**Gatilho para reabrir como B2 (irmãs isoladas):** o negócio demonstrar que Sustainment é vendável **sem**
Asset Management. Nesse momento, `sustainment` ganha `vertical_id` próprio, entra no manifesto e no teste
vertical ⊥ vertical, e `ReserveMaterialForWorkOrder` vira saga (`WAITING_MATERIAL` até `material_reserved`).

**Consequência para o manifesto:** `docs/architecture/verticals.toml` continua registrando **só `asset`**;
`sustainment` **não** entra no teste vertical ⊥ vertical enquanto valer B1. Os `event_namespaces` de `asset`
passam a incluir `sustainment` como sub‑namespace (`asset.sustainment.*`) — um dono só. *(Editar
`verticals.toml` é mudança de Lane C — PR de Shared Integration separado, referenciando esta ADR.)*

### 2. Máquina de estados da `WorkOrder`

Estados (VO enum `WorkOrderState`):

```
DRAFT · PLANNED · READY · SCHEDULED · IN_PROGRESS · TECHNICALLY_COMPLETE · VALIDATION · COMPLETED
estados de espera (reversíveis): WAITING_MATERIAL · WAITING_AUTHORIZATION · WAITING_TECHNICIAN
INTERRUPTED · CANCELLED (terminal, com motivo)
```

`WAITING_MATERIAL` **é um estado próprio** nesta ADR (revisando `05_DOMAIN_MODEL.md` §1.1, que o tratava só
como derivado do veículo): ele precisa ser observável na fila da oficina e disparar o fluxo de transferência
(cenário B). Continua **derivado por condição** — a aplicação entra/sai dele automaticamente conforme
I‑WO‑4, não por comando manual.

Tabela de transições (constituição §16 — origem → destino · ator · permissão · pré‑requisito · evento · motivo):

| # | Origem → Destino | Ator | Permissão | Pré‑requisito | Evento | Motivo |
|---|---|---|---|---|---|---|
| T1 | — → `DRAFT` | planejador | `SUSTAINMENT_WO.OPEN` | veículo autorizado (I‑SEC‑2); `ContractContext` resolvido e congelado (I‑SLI‑1) | `work_order_opened` | — |
| T2 | `DRAFT` → `PLANNED` | planejador | `SUSTAINMENT_WO.ADD_TASK` | ≥1 tarefa; demanda de material registrada | `work_order_state_changed` | — |
| T3 | `PLANNED` → `WAITING_MATERIAL` | sistema | — | `Σ reservado < demandado` e sem estoque atendível local (I‑WO‑4) | `work_order_state_changed` | — |
| T4 | `WAITING_MATERIAL` → `PLANNED` | sistema | — | condição de T3 deixou de valer (recebimento/reserva) | `work_order_state_changed` | — |
| T5 | `PLANNED` → `READY` | planejador/sistema | `SUSTAINMENT_WO.TRANSITION` | todo material demandado reservado (I‑WO‑2); sem espera pendente | `work_order_state_changed` | — |
| T6 | `PLANNED`/`READY` → `WAITING_AUTHORIZATION` | sistema | — | ação exige autorização (ex.: entitlement `DENIED`/exceção) | `work_order_state_changed` | **obrigatório** |
| T7 | `WAITING_AUTHORIZATION` → estado anterior | gestor de contrato | `SUSTAINMENT_WO.TRANSITION` | `Decision` de exceção autorizada (I‑SLI‑5) | `work_order_state_changed` | **obrigatório** |
| T8 | `READY` → `SCHEDULED` | planejador | `SUSTAINMENT_WO.TRANSITION` | técnico e oficina alocados | `work_order_state_changed` | — |
| T9 | `SCHEDULED` → `WAITING_TECHNICIAN` | sistema | — | técnico qualificado indisponível | `work_order_state_changed` | — |
| T10 | `SCHEDULED`/`WAITING_TECHNICIAN` → `IN_PROGRESS` | técnico | `SUSTAINMENT_WO.EXECUTE` | veículo em `IN_MAINTENANCE` (T‑VEH) | `work_order_state_changed`, `vehicle.lifecycle_state_changed` | — |
| T11 | `IN_PROGRESS` → `INTERRUPTED` | técnico | `SUSTAINMENT_WO.EXECUTE` | — | `work_order_state_changed` | **obrigatório** |
| T12 | `INTERRUPTED` → `IN_PROGRESS` | técnico | `SUSTAINMENT_WO.EXECUTE` | — | `work_order_state_changed` | — |
| T13 | `IN_PROGRESS` → `TECHNICALLY_COMPLETE` | técnico | `SUSTAINMENT_WO.TECH_COMPLETE` | toda `WorkTask.mandatory` = `DONE`; `diagnosis`/`root_cause`/`resolution` presentes (I‑WO‑1) | `work_order_technically_complete` | — |
| T14 | `TECHNICALLY_COMPLETE` → `VALIDATION` | validador | `SUSTAINMENT_WO.VALIDATE` | — | `work_order_state_changed` | — |
| T15 | `VALIDATION` → `TECHNICALLY_COMPLETE` | validador | `SUSTAINMENT_WO.VALIDATE` | validação reprovada | `post_maintenance_validated` (result=fail) | **obrigatório** |
| T16 | `VALIDATION` → `COMPLETED` | validador | `SUSTAINMENT_WO.CLOSE` | `PostMaintenanceValidation` passou; nenhuma obrigação aberta (I‑WO‑1) | `post_maintenance_validated`, `work_order_completed`, `vehicle.returned_to_service` | — |
| T17 | qualquer não‑terminal → `CANCELLED` | planejador/gestor | `SUSTAINMENT_WO.CANCEL` | libera reservas vinculadas | `work_order_cancelled`, `inventory.stock_reservation_released` | **obrigatório** |

`COMPLETED` e `CANCELLED` são terminais. Toda transição emite exatamente um evento de estado + registro de
auditoria (I‑WO‑3). Estados de espera são reversíveis e não contam como progresso.

### 3. Autorização OM/Site — **G1 para o slice**

Adota‑se **G1** de `11_AUTHORIZATION_MODEL.md`: `CustomerSite` é entidade de `asset_domain`;
`AssetOperationContext` estende o `OrganizationContext` do Core com `site_scope` (`ALL` ou
`frozenset[CustomerSiteId]`), derivado por uma `Policy`/`Rule` governada; o predicado de escopo é aplicado
**antes** da resolução do dado (I‑SEC‑2); RLS por Organization permanece a barreira dura. **Nenhum conceito
`OM`/`MilitaryOrganization`/`CustomerSite`/`Workshop`/`Vehicle` entra em `packages/core_*` ou
`shared_kernel`** (constituição §18).

**G2 (OM = Organization)** fica registrada como opção a decidir **por contrato**, numa ADR de continuação,
quando existir um cliente cujo OM seja entidade independente com usuários próprios. Não há esse cliente no
primeiro slice, então o slice implementa G1.

Se `site_scope` na vertical se mostrar insuficiente durante A4/A5 (precisar valer para capacidades do Core
consumidas pela vertical), abre‑se **`CORE_CHANGE_REQUEST`** para um `Scope` genérico opcional no
`OrganizationContext`, provando horizontalidade com o caso análogo de Livestock — **nunca** implementado
antes disso.

### 4. Layout de módulos e migrations do slice

```
packages/asset_domain/          Vehicle · VehicleModel/Variant · ConfigurationBaseline/Revision/Effectivity
packages/asset_application/       · Part · PartRevision · Supersession · Applicability · InterchangeabilityGroup
packages/asset_infrastructure/    · StockLocation · StockPosition · StockReservation · StockTransfer · CustomerSite
    persistence/
      metadata.py               = organization_metadata do Core (padrão de livestock_infrastructure)
      migrations/                ambiente Alembic PRÓPRIO (A-M1): env.py com
                                 make_include_object(owned_tokens={"asset"},
                                   fk_allowlist={("core_identity","organizations")}),
                                 branch label "asset", 1ª revisão depends_on -> revisão do Core
                                 que cria core_identity.organizations

packages/sustainment_domain/     SLIContract · ContractVersion · CoverageLine
packages/sustainment_application/ Entitlement (= Evaluation->Decision do Core) · WorkOrder · WorkTask
packages/sustainment_infrastructure/  FailureRecord · PostMaintenanceValidation · WorkshopDashboard (read model)
    persistence/migrations/      ambiente próprio, branch label "sustainment"  (mesmo padrão)
                                 — OU compartilha o de asset se B1 e o negócio não pedir reversão isolada
                                 (decidir em A3)

apps/api/asset/                  routers + dependencies.py (espelha livestock_dependencies.py),
                                 registrado em apps/api/_registry.py (P3, Shared Integration)
apps/validacao/asset/            roteiros executáveis dos cenários A e B (A7)
```

Tabelas no schema `core_audit`, FK compostas por Organization (ADR‑0077), RLS por Organization, carimbo
`titan.module_owner=asset` (token único — evita a inconsistência AR‑14). `sustainment` carimba
`titan.module_owner=sustainment` mesmo sob B1 (ownership lógico distinto; a fronteira de dependência é que é
compartilhada).

### 5. Entitlement é decisão governada do Core (reafirmação vinculante)

O direito a peça/serviço é **sempre** o resultado de `Evaluation → Decision` via
`core_application.{evaluation_service,decision_service,decision_governance_service}`, com fatos tipados,
`context_hash` e uma `Rule` governada de cobertura SLI. **É proibido** haver lógica de cobertura/exclusão/
limite fora de `Rule`/`Evaluation` em `packages/sustainment_*` (I‑SLI‑4). Um teste de `grep` no gate de A4
verifica isso.

---

## O que esta ADR não decide

- O modelo completo da plataforma (produção, procurement, confiabilidade, publicações técnicas, 3D/AR,
  integração ERP/PLM/WMS) — nomeados, fora do slice.
- Se `sustainment` compartilha o ambiente de migrations de `asset` ou tem o próprio — decisão de A3.
- G2 vs G1 para um cliente com OM independente — ADR de continuação.
- Estratégia de `apps/web` de Asset (`18_UX_OPERATING_MODEL.md`, AR‑13).
- O detalhe de `10_TEMPORAL_MODEL.md` e `12_AUDIT_MODEL.md` — diferidos para antes de A4.

---

## Impacto de Segurança

Isolamento por Organization (RLS, role restrita, FK compostas — ADR‑0002/0003/0077) inalterado e verificado
por teste para cada tabela nova. O escopo OM/Site (G1) é aplicado **antes** da resolução do dado; recurso
fora do escopo retorna `404` sem vazar existência (I‑SEC‑2). Autorização por permissão, nunca por papel
(catálogo em `11` §3). Operações privilegiadas (`AdjustStock`, `AmendContract`, `WithdrawPartApplicability`,
`CancelWorkOrder`, transição de ciclo de vida fora do fluxo) exigem `reason` + evento de auditoria dedicado +
`DecisionGovernance` quando a política exigir. Acesso a documento técnico/desenho passa pela mesma checagem
de permissão + escopo. `packages/core_*` não recebe nenhum conceito de Asset.

## Impacto de Auditoria

Toda transição de `WorkOrder`/`WorkTask` e todo movimento de estoque emitem evento append‑only no
`event_log` do Core + registro de auditoria; `CANCELLED`/`INTERRUPTED`/`WAITING_AUTHORIZATION` exigem motivo
(I‑WO‑3). Correções (`*_corrected`, `*_withdrawn`) são aditivas — nunca `UPDATE`/`DELETE` de evento
(constituição §24). O `ContractContext` congelado e o `decision_ref` do entitlement anexados aos eventos da
WO garantem que a auditoria contratual de uma WO histórica use a versão vigente **à época** (cenário E,
I‑SLI‑1). A cadeia de integridade é a garantia global do Core por Organization (decisão F); nenhum código de
Asset toca a semântica de integridade. Dossiê de sustentação usa `core_domain.dossier` +
`VerticalSection` (ADR‑0060).

## Impacto de Migração

`asset` nasce com ambiente Alembic próprio (A‑M1), dependente de S‑M1–S‑M3 da stack
`integration/core/parallel-vertical-foundation` (P0). Tabelas novas apenas; nenhuma migração de Livestock
ou do Core é tocada. `alembic upgrade heads` do zero cria o schema completo; `alembic check` com o `env.py`
de Asset → "no changes"; `pg_dump --schema-only` do schema de Livestock inalterado antes/depois. Rollback:
`downgrade` da *branch label* `asset` isoladamente. `verticals.toml` ganha `sustainment` como sub‑namespace
de evento e (se A3 decidir ambiente próprio) uma `migration_location` — via PR de Shared Integration.

## Implicações de Teste

- Invariantes I‑VEH/CFG/PRT/APP/INV/SLI/WO/SEC com teste de domínio/aplicação (`07_INVARIANTS.md`).
- Máquina de estados: cada transição T1–T17 com teste positivo e negativo (transição não listada → recusa
  com motivo).
- Concorrência de estoque (`ThreadPoolExecutor`+`Barrier` contra Postgres real): I‑INV‑1/3/4.
- Autorização: RLS por tabela sob role restrita; `site_scope` antes da resolução; permissão‑não‑papel
  (`11` §6).
- `grep` de A4: nenhuma lógica de cobertura fora de `Rule`/`Evaluation`; nenhuma string `livestock` em
  `packages/asset_*`/`packages/sustainment_*`/`apps/api/asset/`.
- Integração ponta a ponta A7: cenários A e B respondendo os **16 pontos do §47** com evidência.

---

## Alternativas consideradas

| Alternativa | Motivo da rejeição (para o slice) |
|---|---|
| **B2 — `sustainment` vertical irmã isolada desde já** | `ReserveMaterialForWorkOrder` no cenário A precisaria ser saga; janela de `reservado ≠ demandado` sem falha observável enfraquece I‑WO‑2. Reabrir se Sustainment for vendável sozinho. |
| **Copiar a máquina de estados do Maximo** | Proibido (constituição §16); estados como `APPR`/`WAPPR`/`WSCH` não mapeiam o fluxo real (entitlement governado, `WAITING_MATERIAL` derivado). |
| **`WAITING_MATERIAL` apenas como flag derivada, sem estado** | A oficina precisa vê‑lo na fila e ele dispara o fluxo de transferência (cenário B); flag invisível vira o red flag "status sem máquina de estados" (constituição §42). |
| **G2 (OM = Organization) para o slice** | Sem cliente com OM independente no primeiro contrato; G2 traz identidade/memberships por OM e interage com a cadeia de integridade (H1) sem necessidade comprovada. |
| **G3 (primitiva de escopo no Core) agora** | Especulativa (constituição §38); G1 precisa provar a necessidade primeiro. |
| **Entitlement como serviço próprio com regras da vertical** | Duplica a engine de decisão do Core, não auditável, permite divergência (I‑SLI‑4, constituição §23). |

---

## Critérios de aceitação

- [x] SPEC `docs/asset/specs/approved/2026-09-10-titan-asset-primeiro-slice.md` aprovada pelo dono
  (11/09/2026).
- [x] Esta ADR aprovada pelo dono (11/09/2026) — decisões B, máquina de estados, G1‑do‑slice e layout
  fixadas.
- [x] Discovery (01–09, 11, 19, 20) revisada por um único agente de engenharia (papéis adversarial +
  integração — o dono decidiu em 11/09/2026 que o projeto opera com dono+Claude, sem Codex/Gemini dedicados
  a esta vertical); sem BLOQUEADOR aberto; `MULTI_AGENT_ARCHITECTURE_REVIEW.md` produzido (§49), com 1 HIGH
  e 3 MEDIUM encontrados e corrigidos nos próprios documentos de discovery.
- [x] Decisões A, F, G aceitas em `docs/architecture/DECISIONS_REQUIRED_PHASE0.md` (10–11/09/2026).
- [ ] P0 — merge da stack `integration/core/parallel-vertical-foundation` (G1–G3, S‑M1–S‑M3, P2). **Pendente**
  — stack pronta (10 commits verdes), aguarda revisão/merge do dono.
- Os 16 pontos do §47 exprimíveis como asserções do teste ponta a ponta de A7 — propriedade do desenho,
  já satisfeita pela SPEC; confirma‑se na prática em A7.
- **A2 (primeiro código) começa quando P0 (merge) estiver feito** — é o único item ainda pendente. Discovery,
  revisão e decisões A/B/F/G já estão fechadas.

## Plano de reversão

Enquanto nenhum código for escrito, reverter é marcar este rascunho como `DESCARTADO`. Após A2, cada passo
A* é um PR independente e revertível; A3 (migrations) é o único com cuidado extra (diff de `pg_dump`) e
depende de P0.
