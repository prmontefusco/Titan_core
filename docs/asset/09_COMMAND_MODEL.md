# 09 — COMMAND MODEL — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Comandos com **intenção de negócio explícita** (constituição §28): `POST /work-orders/{id}/reserve-material`,
não `PATCH {materialStatus:"reserved"}`. Cada comando importante define: **autorização · validação ·
versão esperada (concorrência otimista) · idempotência · fronteira de transação · eventos emitidos ·
semântica de auditoria** (constituição §28, §35).

Legenda de colunas: **Autz** = permissão exigida (`<MODULE>.<AÇÃO>`, nunca por papel — constituição §26,
`11_AUTHORIZATION_MODEL.md`); **Ver** = exige `expected_version`; **Idem** = exige chave de idempotência;
**Tx** = fronteira transacional; **Emite** = evento(s) de `08_DOMAIN_EVENTS.md`.

---

## 1. Módulo `asset`

### Vehicle
| Comando | Autz | Ver | Idem | Tx | Valida | Emite |
|---|---|---|---|---|---|---|
| `RegisterVehicle` | `ASSET_VEHICLE.REGISTER` | — | ✔ | `Vehicle` | identifiers únicos por Organization; `site` existe e é autorizado | `vehicle.registered` |
| `SetVehicleConfigurationBaseline` | `ASSET_VEHICLE.SET_BASELINE` | ✔ | ✔ | `Vehicle` | baseline aplicável ao modelo/variante/série; `valid_from` ≥ última | `vehicle.configuration_baseline_set` (I‑VEH‑1) |
| `RecordMeterReading` | `ASSET_VEHICLE.RECORD_METER` | ✔ | ✔ | `Vehicle` | `value` ≥ última do `kind` | `vehicle.meter_reading_recorded` (I‑VEH‑2) |
| `CorrectMeterReading` | `ASSET_VEHICLE.CORRECT_METER` | ✔ | ✔ | `Vehicle` | `reason` obrigatório; original existe | `vehicle.meter_reading_corrected` |
| `TransitionVehicleLifecycle` | `ASSET_VEHICLE.TRANSITION` | ✔ | ✔ | `Vehicle` | transição permitida; `reason` se exigido | `vehicle.lifecycle_state_changed` (I‑VEH‑3) |

### Configuration
| `PublishConfigurationBaseline` | `ASSET_CONFIG.PUBLISH` | ✔ | ✔ | `ConfigurationBaseline` | cadeia acíclica; efetividade não sobrepõe na mesma posição | `configuration.baseline_published` (I‑CFG‑1/2) |
| `SupersedeConfigurationRevision` | `ASSET_CONFIG.SUPERSEDE` | ✔ | ✔ | `ConfigurationBaseline` | `reason`; não cria ciclo | `configuration.baseline_superseded` |

### Part / Applicability
| `RegisterPart` | `ASSET_PART.REGISTER` | — | ✔ | `Part` | `part_number` único por Organization | `part.registered` (I‑INV‑0) |
| `AddPartRevision` | `ASSET_PART.ADD_REVISION` | ✔ | ✔ | `Part` | `revision_code` novo | `part.revision_added` |
| `SupersedePartRevision` | `ASSET_PART.SUPERSEDE` | ✔ | ✔ | `Part` | grafo acíclico; `reason` | `part.revision_superseded`, `part.lifecycle_state_changed` (I‑PRT‑1) |
| `ChangeInterchangeabilityGroup` | `ASSET_PART.EDIT_INTERCHANGE` | ✔ | ✔ | `InterchangeabilityGroup` | simetria preservada | `part.interchangeability_group_changed` (I‑PRT‑2) |
| `AssertPartApplicability` | `ASSET_APPLICABILITY.ASSERT` | — | ✔ | `Applicability` | **`evidence_ref` obrigatório**; `target` bem formado | `applicability.asserted` (I‑APP‑1) |
| `WithdrawPartApplicability` | `ASSET_APPLICABILITY.WITHDRAW` | ✔ | ✔ | `Applicability` | `reason`; gera `correction` | `applicability.withdrawn` (I‑APP‑2) |

### Inventory
| `OpenStockPosition` | `ASSET_INVENTORY.OPEN_POSITION` | — | ✔ | `StockPosition` | `(part, location, purpose)` inédita | `inventory.stock_position_opened` |
| `AdjustStock` | `ASSET_INVENTORY.ADJUST` | ✔ | ✔ | `StockPosition` (FOR UPDATE) | `reason` + `actor`; `delta_by_status` nomeia o(s) bucket(s) alvo (`on_hand`/`in_transit`/`quarantine`/`inspection`/`damaged`) explicitamente — nunca "ajuste genérico"; cada bucket resultante ≥ 0 individualmente, e `available(purpose)` recalculado ≥ 0 | `inventory.stock_adjusted` (I‑INV‑3) |
| `ReserveStock` | `ASSET_INVENTORY.RESERVE` | ✔ | ✔ | `StockPosition` (FOR UPDATE) + `StockReservation` | `available(purpose) ≥ qty`; propósito compatível **ou** `Decision` de disputa; demanda existe | `inventory.stock_reserved` (+ `allocation_decided` se disputa) (I‑INV‑1/2) |
| `ReleaseStockReservation` | `ASSET_INVENTORY.RELEASE` | ✔ | ✔ | `StockReservation` + `StockPosition` | reserva em `HELD`/`ALLOCATED` | `inventory.stock_reservation_released` |
| `AllocateStockReservation` | `ASSET_INVENTORY.ALLOCATE` | ✔ | ✔ | `StockReservation` | reserva `HELD` | `inventory.stock_reservation_allocated` |
| `ConsumeStock` | `ASSET_INVENTORY.CONSUME` | ✔ | ✔ | `StockReservation` + `StockPosition` (FOR UPDATE) | reserva `ALLOCATED`; `qty ≤ reservado`; WO em execução | `inventory.stock_consumed` (I‑WO‑2) |
| `RequestStockTransfer` | `ASSET_INVENTORY.TRANSFER_REQUEST` | ✔ | ✔ | `StockTransfer` | origem tem `available`; destino existe | `inventory.transfer_requested` (I‑INV‑4) |
| `DispatchStockTransfer` | `ASSET_INVENTORY.TRANSFER_DISPATCH` | ✔ | ✔ | `StockTransfer` + `StockPosition` origem (FOR UPDATE) | qty ≤ `on_hand` origem | `inventory.transfer_dispatched` |
| `ReceiveStockTransfer` | `ASSET_INVENTORY.TRANSFER_RECEIVE` | ✔ | ✔ | `StockTransfer` + `StockPosition` destino (FOR UPDATE) | `Σ recebido ≤ despachado` | `inventory.transfer_received` (I‑INV‑4) |

### CustomerSite
| `RegisterCustomerSite` | `ASSET_SITE.REGISTER` | — | ✔ | `CustomerSite` | `code` único por Organization | `site.registered` |

## 2. Módulo `sustainment`

### SLIContract
| `RegisterSLIContract` | `SUSTAINMENT_CONTRACT.REGISTER` | — | ✔ | `SLIContract` | `customer` existe | `contract_registered` |
| `IssueContractVersion` | `SUSTAINMENT_CONTRACT.ISSUE_VERSION` | ✔ | ✔ | `SLIContract` | `effective` não retroage sobre versão já referenciada; `version_no` = atual+1 | `contract_version_issued` (I‑SLI‑3) |
| `AmendContract` | `SUSTAINMENT_CONTRACT.AMEND` | ✔ | ✔ | `SLIContract` | gera nova `ContractVersion` com `amendment_ref` | `contract_version_issued` |

### Entitlement
| `ResolveEntitlement` | `SUSTAINMENT_ENTITLEMENT.RESOLVE` | — | ✔ | leitura + `Evaluation`/`Decision` do Core (transação do Core) | fatos tipados montados; versão do contrato selecionada por tempo **antes** da regra (I‑SLI‑2) | `entitlement_resolved` (I‑SLI‑1/4/5) |

`ResolveEntitlement` **não** grava verdade da vertical: delega a `core_application.evaluation_service` +
`decision_service` (+ `decision_governance_service` quando exigido). O `decision_ref` volta e é anexado ao
comando da WO que o consome.

| `AuthorizeEntitlementException` | `SUSTAINMENT_ENTITLEMENT.AUTHORIZE_EXCEPTION` | — | ✔ | `Decision` do Core (`decision_governance_service`) + `WorkOrder` (T7) | entitlement original = `DENIED`; `reason` obrigatório; ator tem `SUSTAINMENT_ENTITLEMENT.AUTHORIZE_EXCEPTION` (gestor de contrato, não o mesmo papel que abriu a WO) | `entitlement_resolved` (outcome `GRANTED_WITH_EXCEPTION`) |

Achado da revisão adversarial (`MULTI_AGENT_ARCHITECTURE_REVIEW.md`): a máquina de estados da WO
(`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` §2, transição T7) referenciava
"gestor de contrato autoriza exceção" sem comando correspondente — `AuthorizeEntitlementException` fecha essa
lacuna. É ele quem produz o `Decision` de exceção que T7 exige e que `ReserveMaterialForWorkOrder`/
`I‑SLI‑5` verificam antes de aceitar um entitlement `GRANTED_WITH_EXCEPTION`.

### WorkOrder
| Comando | Autz | Ver | Idem | Tx | Valida | Emite |
|---|---|---|---|---|---|---|
| `OpenWorkOrder` | `SUSTAINMENT_WO.OPEN` | — | ✔ | `WorkOrder` (+ leitura de `SLIContract` p/ congelar contexto) | veículo existe e é autorizado (I‑SEC‑2); resolve **1** `ContractVersion`+`CoverageLine` ativa → congela `ContractContext` | `work_order_opened` (I‑SLI‑1) |
| `AddWorkOrderTask` | `SUSTAINMENT_WO.ADD_TASK` | ✔ | ✔ | `WorkOrder` | WO não terminal | `work_order_task_added` |
| `DemandMaterial` | `SUSTAINMENT_WO.DEMAND_MATERIAL` | ✔ | ✔ | `WorkOrder` | tarefa existe; `part_ref` existe | `material_demanded` |
| `ReserveMaterialForWorkOrder` | `SUSTAINMENT_WO.RESERVE_MATERIAL` | ✔ | ✔ | **operação coordenada** `sustainment`+`asset` (B1: mesma tx; B2: saga por evento). Quando a WO demanda **mais de uma** `StockPosition`, os `FOR UPDATE` são adquiridos em ordem determinística (`stock_position_id` crescente) para não depender de detecção de deadlock do Postgres entre duas `WorkOrder`s com demandas sobrepostas em ordens diferentes — achado da revisão adversarial | entitlement da peça = `GRANTED*` (I‑SLI‑4); chama `asset_application.ReserveStock`; `Σ reservado ≤ demandado` (I‑WO‑2) | `material_reserved` (+ `inventory.stock_reserved`) |
| `RecalculateWorkOrderPriority` | `SUSTAINMENT_WO.RECALC_PRIORITY` (ou automático por evento) | ✔ | ✔ | `WorkOrder` + `Evaluation` (Rule governada) | fatores como fatos | `work_order_priority_recalculated` (I‑WO‑5) |
| `TransitionWorkOrder` | `SUSTAINMENT_WO.TRANSITION` | ✔ | ✔ | `WorkOrder` | transição permitida; `reason` se exigido; guarda de `WAITING_MATERIAL` (I‑WO‑4) | `work_order_state_changed` |
| `StartTask` / `CompleteTask` | `SUSTAINMENT_WO.EXECUTE` | ✔ | ✔ | `WorkOrder` | WO em `IN_PROGRESS`; tarefa no estado certo | `task_started` / `task_completed` |
| `RecordRemovedComponent` | `SUSTAINMENT_WO.RECORD_REMOVAL` | ✔ | ✔ | `WorkOrder` | `disposition` válida | `component_removed` (I‑PRT‑1) |
| `RecordTechnicalCompletion` | `SUSTAINMENT_WO.TECH_COMPLETE` | ✔ | ✔ | `WorkOrder` | toda tarefa obrigatória `DONE`; `diagnosis`/`root_cause`/`resolution` presentes | `work_order_technically_complete` |
| `PerformPostMaintenanceValidation` | `SUSTAINMENT_WO.VALIDATE` | ✔ | ✔ | `WorkOrder` | WO `TECHNICALLY_COMPLETE`; resultado registrado | `post_maintenance_validated` (I‑WO‑1) |
| `CloseWorkOrder` | `SUSTAINMENT_WO.CLOSE` | ✔ | ✔ | `WorkOrder` (+ coordena `Vehicle.ReturnToService`) | validação passou; nenhuma obrigação aberta | `work_order_completed`, `vehicle.returned_to_service` (I‑WO‑1, I‑VEH‑3) |
| `CancelWorkOrder` | `SUSTAINMENT_WO.CANCEL` | ✔ | ✔ | `WorkOrder` (+ libera reservas) | `reason` **obrigatório**; WO não terminal | `work_order_cancelled` (+ `inventory.stock_reservation_released`) (I‑WO‑3) |
| `RecordFailure` | `SUSTAINMENT_WO.RECORD_FAILURE` | ✔ | ✔ | `WorkOrder` | modo/posição válidos | `failure_recorded` |

## 3. Comandos de leitura (queries — não emitem evento)

| Query | Autz | Responde |
|---|---|---|
| `GetVehicle(vehicle_id)` | `ASSET_VEHICLE.READ` | detalhe de um veículo (identifiers, baseline vigente, estado, leituras recentes, cobertura) — **achado da revisão de integração**: sem esta query um técnico/planejador não abre a tela de um veículo específico, só a lista (`GetFleetView`) |
| `GetVehicleConfigurationAt(vehicle, instant)` | `ASSET_VEHICLE.READ` | baseline vigente no instante (constituição §25) |
| `ResolvePartApplicability(part, vehicle, instant)` | `ASSET_APPLICABILITY.READ` | asserção(ões) + `evidence_ref`, nunca só `true` (I‑APP‑1, cenário F) |
| `GetAvailability(part, location, purpose)` | `ASSET_INVENTORY.READ` | `AvailabilityBreakdown` (on_hand, reservado por demanda, quarantine, …) |
| `GetWorkOrder(work_order_id)` | `SUSTAINMENT_WO.READ` | detalhe de uma Work Order (tarefas, demanda/reserva de material, contexto contratual congelado, breakdown de prioridade, o que bloqueia) — **achado da revisão de integração**: mesma lacuna de `GetVehicle`, mas para WO; o dashboard lista, esta query abre |
| `GetWorkshopDashboard(site, workshop)` | `SUSTAINMENT_DASHBOARD.READ` | fila de WO ordenada por `PriorityScore` **com breakdown** e o que bloqueia cada uma |
| `GetFleetView(site?)` | `ASSET_VEHICLE.READ` | frota por estado (disponível/degradado/manutenção/indisponível/aguardando material/risco de SLA) — read model citado em `05_DOMAIN_MODEL.md` §1.1 ao lado do `WorkshopDashboard` |
| `GetContractContextForVehicle(vehicle, instant)` | `SUSTAINMENT_CONTRACT.READ` | contrato → versão → cobertura → SLA aplicável no instante, para **um** veículo |
| `GetContractSLASummary(contract_ref)` | `SUSTAINMENT_CONTRACT.READ` | frota coberta, WOs abertas e status de SLA agregado **sob um contrato** — **achado da revisão de integração**: sem esta query, o gestor de contrato SLI (persona de `11_AUTHORIZATION_MODEL.md` §1: "acompanha SLA/cobertura... de tudo sob aqueles contratos") só teria a versão per‑veículo, não a visão que o papel realmente precisa |

## 4. Semântica transversal (constituição §28, §35)

- **Autorização antes da resolução** (constituição §26): o comando/query valida permissão **e**
  `site_scope` (I‑SEC‑2) antes de qualquer `SELECT` de dado de negócio.
- **`expected_version`**: comandos de mutação em agregado com `version` retornam `409` +
  `OptimisticConcurrencyConflict` em divergência.
- **Idempotência**: chave por comando externo; repetição compatível retorna o mesmo resultado (padrão
  `core_application.idempotency`, ADR‑0039‑style).
- **Fronteira de transação**: um comando = uma unidade de trabalho de **uma** vertical
  (`MULTI_VERTICAL_CI_GATES.md` §8). `ReserveMaterialForWorkOrder` é a única operação inter‑módulo; no B1
  roda em transação única `asset`+`sustainment`, no B2 vira saga.
- **Auditoria**: todo comando de mutação relevante deixa evidência no `event_log` do Core; correções são
  eventos aditivos, nunca `UPDATE`/`DELETE` (constituição §24).
- **API de capacidade, não de campo**: rotas espelham comandos (`POST /work-orders/{id}/reserve-material`,
  `POST /stock-positions/{id}/adjust`), não `PATCH` de atributo (constituição §28).
