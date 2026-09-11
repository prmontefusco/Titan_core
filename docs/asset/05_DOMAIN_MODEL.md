# 05 — DOMAIN MODEL — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Entidades, value objects e relações do corte do slice. Agregados e fronteiras transacionais em
`06_AGGREGATE_ANALYSIS.md`; invariantes em `07_INVARIANTS.md`. Notação: **E** entidade, **VO** value object,
**→id** referência por identificador opaco (`shared_kernel.TypedId`), nunca por objeto.

Regra de modelagem (constituição §42, `AGENTS.md`): sem booleano derivado sem derivação
(`is_available`, `is_compatible` proibidos); sem `metadata` genérico escondendo conceito; sem JSON blob para
evitar modelar; string de status só com máquina de estados.

---

## 1. Módulo `asset`

### 1.1 Vehicle *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `vehicle_id` | `VehicleId` (VO) | id opaco |
| `organization_id` | →id `Organization` *(Core)* | tenant; FK composta por Organization (ADR‑0077) |
| `site_id` | →id `CustomerSite` \| null | OM/site de alocação (decisão G) |
| `model` | →id `VehicleModel` | dado, não código |
| `variant` | →id `VehicleVariant` \| null | — |
| `identifiers` | `VehicleIdentifiers` (VO) | `serial_number`, `chassis`, `fleet_number` |
| `current_baseline_ref` | →id `ConfigurationBaseline` | **exatamente uma** vigente em T (I‑CFG‑1) |
| `lifecycle_state` | `VehicleLifecycleState` (VO enum) | `AVAILABLE`/`DEGRADED`/`MAINTENANCE_PLANNED`/`IN_MAINTENANCE`/`UNAVAILABLE`; `WAITING_MATERIAL` é **derivado** da WO, não estado próprio |
| `ownership` | `AssetOwnership` (VO) | `company` / `customer` / other |
| `contract_coverage_ref` | →id `SLIContract` \| null | resolução detalhada em `sustainment` |
| `meter_readings` | lista de `MeterReading` (VO, append‑only) | `kind` (`HOURS`/`KILOMETERS`), `value`, `observed_at`, `recorded_at`, `source` |
| `version` | `int` | concorrência otimista |

`MeterReading` **VO**: imutável; nova leitura ≥ última do mesmo `kind` salvo `CorrectionEvent` (I‑VEH‑2).

### 1.2 VehicleModel / VehicleVariant *(E, dados de referência)*
`model_id`/`variant_id`, `organization_id` (ou compartilhado pela operadora — decisão de A1), `code`,
`display_name`, `systems` (lista rasa de `SystemDefinition` VO para uma falha apontar posição). **Sem**
hierarquia profunda no slice.

### 1.3 ConfigurationBaseline *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `baseline_id` | `ConfigurationBaselineId` | — |
| `organization_id` | →id `Organization` | — |
| `model` / `variant` | →id | a que se aplica |
| `revision` | `ConfigurationRevision` (VO) | `number`, `supersedes_ref` \| null — cadeia **acíclica** (I‑CFG‑2) |
| `effectivity` | `Effectivity` (VO) | `serial_range` (VO: `from`/`to` \| open), `valid_from`/`valid_to` (tempo válido); intervalos **não sobrepõem** para a mesma `position` (I‑CFG‑3) |
| `positions` | lista de `BaselinePosition` (VO) | `position_code`, `part_ref` →id `Part`, `part_revision_ref` →id `PartRevision` |
| `view` | `ConfigurationView` (VO enum) | `AS_DESIGNED` / `AS_BUILT` / `AS_MAINTAINED` |
| `version` | `int` | — |

### 1.4 Part *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `part_id` | `PartId` | — |
| `organization_id` | →id `Organization` | catálogo por tenant |
| `identity` | `PartIdentity` (VO) | `part_number`, `description`, `manufacturer`, `manufacturer_pn`, `nsn` \| null, `external_classifications` |
| `revisions` | lista de `PartRevision` (E interna) | `revision_code`, `spec_ref`, `drawing_ref`, `materials`, `lifecycle_state` |
| `supersessions` | lista de `Supersession` (VO) | `predecessor_revision`, `successor_revision`; grafo **acíclico** (I‑PRT‑1) |
| `interchangeability_group_ref` | →id `InterchangeabilityGroup` \| null | pertinência simétrica (I‑PRT‑2) |
| `lifecycle_state` | `PartLifecycleState` (VO enum) | `ACTIVE`/`SUPERSEDED`/`OBSOLETE`/`ALTERNATE` |
| `version` | `int` | — |

**Part não tem quantidade.** Existir ≠ ter estoque (constituição §8, I‑INV‑0).

### 1.5 Applicability *(E, raiz de agregado própria — não é campo de `Part`)*

| Campo | Tipo | Nota |
|---|---|---|
| `applicability_id` | `ApplicabilityId` | — |
| `organization_id` | →id `Organization` | — |
| `part_ref` / `part_revision_ref` | →id | o que se aplica |
| `target` | `ApplicabilityTarget` (VO) | `model`/`variant`/`serial_range`/`config_position`/`effectivity` |
| `evidence_ref` | →id `Evidence` *(Core `core_domain.evidence`)* | **obrigatório** — sem evidência não há asserção (I‑APP‑1) |
| `asserted_at` / `asserted_by` | temporal + →id | quando/quem |
| `state` | `ApplicabilityState` (VO enum) | `ASSERTED` / `WITHDRAWN` (com `CorrectionEvent`) |

Consulta "esta peça serve neste veículo nesta config?" = resolver `Applicability` **ativas** cujo `target`
casa com `(model, variant, serial, baseline.position)` no instante — retorna a asserção + evidência, nunca
só `true`.

### 1.6 InterchangeabilityGroup *(E)*
`group_id`, `organization_id`, `member_part_revisions` (lista →id). Pertencer ao grupo é simétrico:
qualquer membro substitui qualquer membro sob as condições do grupo (I‑PRT‑2).

### 1.7 StockLocation *(E)*
`location_id`, `organization_id`, `site_id` →id `CustomerSite` \| null, `kind` (`CENTRAL_WAREHOUSE`/
`REGIONAL_WAREHOUSE`/`WORKSHOP`/`OM_STOCK`), `code`, `display_name`.

### 1.8 StockPosition *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `stock_position_id` | `StockPositionId` | — |
| `organization_id` | →id `Organization` | — |
| `part_ref` | →id `Part` | — |
| `location_ref` | →id `StockLocation` | — |
| `purpose` | `StockPurpose` (VO enum) | `PRODUCTION`/`SERVICE_SLI`/`OM_REMOTE`/`COMMERCIAL` |
| `lot` / `serial` | `LotId` \| null / `SerialId` \| null | quando exigido |
| `ownership` | `StockOwnership` (VO enum) | `COMPANY_OWNED`/`CUSTOMER_OWNED`/`CONSIGNMENT` |
| `quantities` | `StockQuantities` (VO) | `on_hand`, `in_transit`, `quarantine`, `inspection`, `damaged` — todos ≥ 0 |
| `reservations` | lista de `StockReservationLine` (VO) | `reservation_id`, `demand_ref`, `qty`, `priority`, `purpose_lock` |
| `version` | `int` | concorrência otimista **obrigatória** (I‑INV‑3) |

`available(purpose) = on_hand − Σ reservations.qty − quarantine − inspection − damaged`, calculado, nunca
armazenado como booleano (I‑INV‑1). `AvailabilityBreakdown` (VO) é a resposta explicável.

### 1.9 StockReservation *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `reservation_id` | `StockReservationId` | — |
| `organization_id` | →id `Organization` | — |
| `stock_position_ref` | →id `StockPosition` | — |
| `demand` | `DemandRef` (VO) | `kind` (`WORK_ORDER`/`PRODUCTION_ORDER`/`SALES_ORDER`), `ref` →id |
| `qty` | `Quantity` | — |
| `purpose` | `StockPurpose` | deve casar com o da posição, salvo política que autorize |
| `priority` | `ReservationPriority` (VO) | usada na disputa (cenário C) |
| `state` | `ReservationState` (VO enum) | `HELD` / `ALLOCATED` / `CONSUMED` / `RELEASED` |
| `decision_ref` | →id `Decision` *(Core)* \| null | quando a alocação envolveu disputa/política — a decisão explicável (I‑INV‑2) |
| `version` | `int` | — |

### 1.10 StockTransfer *(E, raiz de agregado)* — cenário B
`transfer_id`, `organization_id`, `part_ref`, `from_location_ref`, `to_location_ref`, `qty`, `state`
(`REQUESTED`/`DISPATCHED`/`IN_TRANSIT`/`PARTIALLY_RECEIVED`/`RECEIVED`), `linked_reservation_ref` →id \|
null (a reserva que a transferência serve). Custódia em trânsito referencia `core_domain.provenance`.

### 1.11 CustomerSite *(E)* — OM/Site (decisão G)
`site_id`, `organization_id`, `customer_ref`, `code`, `display_name`, `kind` (`OM`/`CIVIL_FLEET_SITE`/…),
`contacts` (VO). **Vive na vertical**; nenhum equivalente entra no Core. É o valor do `site_scope` no
contexto de autorização (`11_AUTHORIZATION_MODEL.md`).

---

## 2. Módulo `sustainment`

### 2.1 SLIContract *(E, raiz de agregado)*

| Campo | Tipo | Nota |
|---|---|---|
| `contract_id` | `SLIContractId` | — |
| `organization_id` | →id `Organization` (operadora/fornecedor) | — |
| `customer_ref` | →id `Customer` | — |
| `versions` | lista de `ContractVersion` (E interna, append‑only) | ver 2.2 |
| `current_version_no` | `int` | ponteiro; versões antigas **imutáveis** (I‑SLI‑3) |

### 2.2 ContractVersion *(E interna de `SLIContract`)*

| Campo | Tipo | Nota |
|---|---|---|
| `version_no` | `int` | monotônico |
| `effective` | `KnownValidInterval` (VO) | tempo válido (vigência) + tempo de conhecimento (`shared_kernel.temporal`) |
| `coverage_lines` | lista de `CoverageLine` (VO) | `scope` (`model`/`vehicle`/`site`/`region`), `covered_services`, `covered_parts`, `excluded_parts`, `labor_rules`, `travel_rules` |
| `response_sla` / `repair_sla` | `SLA` (VO) | `duration`, `clock_start_event`, `clock_stop_event`, `pause_conditions` |
| `availability_target` | `Percentage` \| null | medição fora do slice |
| `service_limits` | `ServiceLimits` (VO) | tetos por período |
| `amendment_ref` | →id `ContractAmendment` \| null | o que originou esta versão |

### 2.3 Entitlement *(não é entidade persistida como verdade — é o resultado de uma `Evaluation → Decision` do Core)*

Resolver entitlement de um `(vehicle, part | service, instant)`:

1. `sustainment_application` monta os **fatos** (`Fact`): veículo, OM, contrato ativo no instante, versão do
   contrato aplicável (seleção temporal — I‑SLI‑1/2), cobertura, exclusões, limites consumidos.
2. Submete a uma `Rule` **governada** (`core_domain.rule` + `rule_governance`) → produz `Evaluation`
   (`context_hash`, fotografia normativa tipada).
3. `Evaluation` → `Decision` explicável (`+coberto pela linha X`, `−peça excluída`, `−limite de serviço
   atingido`), com `DecisionGovernance` quando exigido.
4. O `Decision` é **anexado** ao evento da Work Order que o consumiu; nunca recalculado com a versão de
   hoje (I‑SLI‑1, cenário E).

`Entitlement` (VO de leitura) = projeção do último `Decision` para aquele par, com `decision_ref` para
rastreio. **É o teste mais forte de reuso do Core** (`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §6).

### 2.4 WorkOrder *(E, raiz de agregado — o coração transacional)*

| Campo | Tipo | Nota |
|---|---|---|
| `work_order_id` | `WorkOrderId` | — |
| `organization_id` | →id `Organization` | — |
| `vehicle_ref` | →id `Vehicle` | referência, não composição |
| `site_ref` | →id `CustomerSite` | onde |
| `workshop_ref` | →id `Workshop` \| null | — |
| `contract_context` | `ContractContext` (VO) | `contract_ref`, `contract_version_no`, `resolved_at` — **congelado** na abertura (I‑SLI‑1) |
| `failure` | `FailureRecord` (VO leve) | `mode`, `reported_at`, `affected_position` |
| `tasks` | lista de `WorkTask` (E interna) | `task_id`, `description`, `mandatory` (bool factual, não derivado), `state`, `labor_entries` |
| `material_demands` | lista de `MaterialDemand` (VO) | `part_ref`, `qty`, `task_id` |
| `material_reservations` | lista de →id `StockReservation` | Σ qty reservada ≤ Σ qty demandada (I‑WO‑2) |
| `state` | `WorkOrderState` (VO enum) | ver §3 |
| `priority` | `PriorityScore` (VO) | ver §4 — determinístico, explicável |
| `diagnosis` / `root_cause` / `resolution` | VO \| null | preenchidos no fechamento técnico |
| `removed_components` | lista de `RemovedComponentDisposition` (VO) | `part_ref`, `serial`, `disposition` |
| `validation` | `PostMaintenanceValidation` (VO) \| null | obrigatória antes de `COMPLETED` (I‑WO‑1) |
| `version` | `int` | concorrência otimista |

### 2.5 WorkshopDashboard *(read model — projeção, não agregado)*
Serviço de projeção em `sustainment_application` + repositório de leitura em `sustainment_infrastructure`.
Alimentado por eventos de `WorkOrder`, `StockReservation`, `Vehicle`, `SLIContract`. Responde "o que a
oficina faz a seguir" ordenando por `PriorityScore` com o breakdown visível. **Não cria agregado nem
contexto** (constituição §21B, §45).

### 2.6 FleetView *(read model — projeção, não agregado)*
Segundo read model do slice, citado em `08_DOMAIN_EVENTS.md` §3 e servido por `GetFleetView`
(`09_COMMAND_MODEL.md` §3) — nomeado aqui explicitamente após a revisão de integração ter notado que só
aparecia nos documentos de eventos/comandos, não no modelo de domínio. Serviço de projeção em
`asset_application` + repositório de leitura em `asset_infrastructure`. Alimentado por eventos de `Vehicle`
(`lifecycle_state_changed`) e `WorkOrder` (para o sinal `WAITING_MATERIAL`/risco de SLA). Responde "como está
a frota" por estado (disponível/degradado/manutenção/indisponível), opcionalmente filtrado por `site` — é
como a persona "planejador"/"representante da OM" de `11_AUTHORIZATION_MODEL.md` §1 enxerga a frota sob seu
`site_scope`. **Não cria agregado nem contexto.**

---

## 3. Máquina de estados da `WorkOrder` (candidata — a derivar em `07`/A1, não copiada de Maximo — §16)

```
DRAFT ─▶ PLANNED ─▶ READY ─▶ SCHEDULED ─▶ IN_PROGRESS ─▶ TECHNICALLY_COMPLETE ─▶ VALIDATION ─▶ COMPLETED
   │         │         │                      │                                                     
   │         ▼         ▼                      ▼                                                     
   │   WAITING_MATERIAL / WAITING_AUTHORIZATION / WAITING_TECHNICIAN        INTERRUPTED ──▶ IN_PROGRESS
   │         (estados de espera, reversíveis)                                                        
   └──────────────────────────▶ CANCELLED (de qualquer estado não terminal, com motivo)
```

Cada transição define (constituição §16): estados de origem permitidos · destino · ator · autorização ·
pré‑requisitos · evento emitido · registro de auditoria · motivo quando exigido. `WAITING_MATERIAL` entra
quando `Σ reservado < Σ demandado` e há demanda não atendível localmente (cenário B).

## 4. `PriorityScore` — motor de prioridade explicável (constituição §22, §21B)

Determinístico, versionado, testável, inspecionável, sem IA. Exemplo de composição (fatores e pesos a
**governar** por `Rule` versionada, dentro de limites):

```
PriorityScore = Σ fatores  (0..100)
  +30  criticidade de missão/segurança do veículo
  +25  SLA de reparo < 8h restantes
  +20  veículo indisponível (não só degradado)
  +10  material necessário disponível (executável agora)
  +7   técnico qualificado disponível
  ... (demais fatores governados)
```

A UI mostra **por que** um item vem antes de outro (o breakdown), nunca só o número. A regra de composição
é uma `Rule` governada → o score tem `evaluation_ref` para auditoria.

---

## 5. Referências entre agregados (sempre por id, nunca navegação de objeto)

```
WorkOrder ──vehicle_ref──▶ Vehicle ──current_baseline_ref──▶ ConfigurationBaseline
WorkOrder ──contract_context.contract_ref──▶ SLIContract (+ version_no congelado)
WorkOrder ──material_reservations──▶ StockReservation ──stock_position_ref──▶ StockPosition ──part_ref──▶ Part
Applicability ──part_ref / part_revision_ref──▶ Part
Vehicle / StockLocation ──site_id──▶ CustomerSite
```

Colaboração `sustainment` → `asset` é **chamada de serviço** (`asset_application`), não acesso a
repositório nem a tabela (`DEPENDENCY_RULES.md`, `PARALLEL_VERTICAL_SAFETY`).
