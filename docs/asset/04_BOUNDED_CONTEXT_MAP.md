# 04 — BOUNDED CONTEXT MAP — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Deriva de `02_DOMAIN_DISCOVERY.md`. Critério de corte: **onde um invariante transacional deixa de valer**
(`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §2), não o nome do subdomínio. Não vira sete pacotes vazios
(constituição §38).

---

## 1. Contextos candidatos avaliados (constituição §39)

| Candidato | Invariante central | Decisão do slice |
|---|---|---|
| Asset Management | Um `Vehicle` tem 1 `ConfigurationBaseline` efetiva em T; ciclo de vida monotônico e auditável | **`asset` (núcleo)** |
| Product Configuration | Cadeia de revisão acíclica; efetividade não sobrepõe para a mesma posição | **junto de `asset`** no início (mesma transação "montar baseline") |
| Parts Engineering | Supersessão acíclica; intercambiabilidade simétrica no grupo | **junto de `asset`** (mesma transação de aplicabilidade) |
| Inventory | `available = on_hand − reserved − … ≥ 0` por `(peça, localização, propósito)`; nenhuma reserva sem quantidade | **`asset`** — mesma transação que cria a reserva a partir da demanda da WO; **módulo próprio só se a reserva virar assíncrona** |
| Logistics / cadeia de custódia | Custódia sem buraco temporal; transferência preserva proveniência | **não é módulo novo** — reutiliza `core_domain.provenance` / `relations` |
| Maintenance | WO não fecha com tarefa obrigatória aberta; reservado ≤ demandado; toda transição emite evento | **`sustainment`** |
| SLI / Sustainment Contracts | WO resolve para **1** linha de contrato ativa no instante do serviço; entitlement ≤ cobertura | **`sustainment`** |
| Procurement, Production Material, Reliability, Technical Publications, Analytics, Integration | — | **nomeados, fora do slice** (constituição §13, §14, §19) |

## 2. Corte inicial: **dois módulos, uma vertical**

```
packages/asset_{domain,application,infrastructure}
    Vehicle · VehicleModel/Variant · ConfigurationBaseline/Revision/Effectivity
    Part · PartRevision · Supersession · Applicability · InterchangeabilityGroup
    StockLocation · StockPosition · StockReservation · StockTransfer

packages/sustainment_{domain,application,infrastructure}
    SLIContract · ContractVersion · CoverageLine · Entitlement
    WorkOrder · WorkTask · MaterialDemand · FailureRecord · PostMaintenanceValidation
    WorkshopDashboard (projeção de leitura — NÃO é contexto novo)
```

**`asset` ↔ `sustainment` cruzam só por referência** (uma `WorkOrder` aponta para um `Vehicle` e consome
`StockPosition`), **nunca por transação compartilhada**. A fronteira entre os dois módulos é limpa desde o
início.

## 3. Decisão B (pendente — `DECISIONS_REQUIRED_PHASE0.md`)

`sustainment_*` pode importar `asset_*`?

- **Recomendação (B1):** tratar `asset` e `sustainment` como **um único `vertical_id = asset`** com dois
  pacotes internos que **podem se referenciar** (`sustainment_application` → `asset_application` para ler
  disponibilidade e aplicabilidade). A fronteira externa verificada por CI é **`asset` ⊥ `livestock`**.
- **Gatilho para virar irmãs isoladas (B2):** o negócio mostrar que Sustainment é vendável **sem** Asset
  Management. Aí `sustainment` ganha `vertical_id` próprio e a colaboração passa a ser por **evento
  publicado / contrato público** (`DEPENDENCY_RULES.md` §6).
- **Formalização:** na ADR do primeiro slice (A1 do `20_EXECUTION_ROADMAP.md`), a partir dos invariantes.
  Até lá, `verticals.toml` registra só `asset`; `sustainment` não entra no teste vertical ⊥ vertical.

## 4. Relações entre contextos (context map)

| De → Para | Tipo de relação | Contrato |
|---|---|---|
| `sustainment` → `asset` | **Customer/Supplier** (B1: import direto de superfície pública de `asset_application`) | `asset_application` expõe: resolver aplicabilidade de peça a veículo; calcular disponibilidade por propósito; criar/consumir `StockReservation` a partir de uma demanda |
| `sustainment` → Core | **Conformist** com contratos do Core | `Evaluation`/`Decision`/`DecisionGovernance` para `Entitlement`; `event_log`; `Dossier`+`VerticalSection` para dossiê contratual; `outbox` |
| `asset` → Core | **Conformist** | Identidade/`OrganizationContext`; `provenance`/`relations` para custódia; `Correction`/`Supersession` (mecânica); `event_log`; `shared_kernel` |
| `asset`/`sustainment` → Livestock | **proibido** (`PARALLEL_VERTICAL_SAFETY`) | nenhum |
| Frontend (`apps/web`) → `asset`/`sustainment` | **via API HTTP apenas** | o frontend **não** possui lógica de aplicabilidade, disponibilidade ou prioridade (cenário F, constituição §43) |
| ERP / PLM / WMS externos → `asset`/`sustainment` | **Anticorruption Layer** (adapter na vertical) | fora do slice; o contrato de integração é propriedade da vertical (`ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §3) |

## 5. Ownership de conceito

| Conceito | Dono | Nota |
|---|---|---|
| `Vehicle`, `Part`, `ConfigurationBaseline`, `StockPosition`, `StockReservation` | `asset` | — |
| `SLIContract`, `ContractVersion`, `Entitlement`, `WorkOrder`, `FailureRecord` | `sustainment` | `Entitlement` **usa** `Evaluation`/`Decision` do Core |
| `CustomerSite` (OM/Site) | `asset` | decisão G; **não** vai para o Core |
| Custódia / proveniência de peça em trânsito | Core (`provenance`/`relations`) | a vertical referencia, não reimplementa |
| Cadeia de integridade de eventos | Core (garantia global por Organization) | decisão F; a vertical só **emite** eventos |
| Máquina de estados / workflow de WO | `sustainment_application` | o Core **não** fornece motor de workflow (`CORE_REUSE_ASSESSMENT.md` §3.6) |
| Notificação a oficina/cliente | `sustainment_application` (projeção + outbox) | candidata a capacidade horizontal do Core quando a 2ª consumidora aparecer — não extrair antes |

## 6. O que este mapa deliberadamente não decide

- A máquina de estados final da `WorkOrder` (deriva na modelagem — `05`/`07`).
- Se `Inventory` vira módulo próprio (só se a reserva virar assíncrona/cross‑warehouse).
- Estrutura de `apps/web` multi‑vertical.
- Formato dos contratos de integração externa.
