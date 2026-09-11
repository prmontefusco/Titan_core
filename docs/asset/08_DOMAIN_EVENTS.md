# 08 — DOMAIN EVENTS — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Eventos de domínio append‑only emitidos pelos agregados de `05_DOMAIN_MODEL.md`. Persistidos via
`core_infrastructure.persistence.events` (cadeia de integridade **por agregado** —
`(organization, aggregate_type, aggregate_id)`, decisão F resolvida e confirmada por teste de concorrência
real em `tests/integration/test_domain_events_postgresql.py`; nenhuma serialização entre agregados
diferentes, mesmo na mesma Organization); entregues via `outbox`. Cada evento carrega `organization_id`, `occurred_at`, `known_at`, `actor_ref`, `aggregate_ref`,
`aggregate_version`, `correlation_id` (constituição §44).

**Namespace** (`MULTI_VERTICAL_CI_GATES.md` §7; manifesto `verticals.toml`): prefixo `asset.` para a
vertical; sub‑namespaces `asset.inventory.*` e `asset.sustainment.*`. Enquanto a decisão B não define se
`sustainment` é vertical própria, os eventos de sustentação usam `asset.sustainment.*` (um dono só). Cada
`message_type` tem exatamente um agregado dono.

---

## 1. Módulo `asset`

### Vehicle
| Evento | Quando | Payload essencial | Invariante relacionado |
|---|---|---|---|
| `asset.vehicle.registered` | veículo criado | `vehicle_id`, `model`, `variant`, `identifiers`, `site_id`, `ownership` | I‑VEH‑1 |
| `asset.vehicle.configuration_baseline_set` | baseline vigente definida/trocada | `vehicle_id`, `baseline_ref`, `valid_from`, `previous_baseline_ref`, `previous_valid_to` | I‑VEH‑1 |
| `asset.vehicle.meter_reading_recorded` | nova leitura | `vehicle_id`, `kind`, `value`, `observed_at`, `source` | I‑VEH‑2 |
| `asset.vehicle.meter_reading_corrected` | correção de leitura | `vehicle_id`, `original_reading_ref`, `corrected_value`, `reason` | I‑VEH‑2 |
| `asset.vehicle.lifecycle_state_changed` | transição de estado | `vehicle_id`, `from_state`, `to_state`, `reason?`, `work_order_ref?` | I‑VEH‑3 |
| `asset.vehicle.returned_to_service` | veículo volta a `AVAILABLE` | `vehicle_id`, `work_order_ref`, `validation_ref` | I‑VEH‑3, I‑WO‑1 |

### Configuration
| `asset.configuration.baseline_published` | nova baseline publicada | `baseline_id`, `model`, `variant`, `revision`, `effectivity`, `supersedes_ref?` | I‑CFG‑1/2 |
| `asset.configuration.baseline_superseded` | revisão substituída | `baseline_id`, `superseded_by_ref`, `reason` | I‑CFG‑1 |

### Part / Applicability
| `asset.part.registered` | peça criada no catálogo | `part_id`, `identity` | I‑INV‑0 |
| `asset.part.revision_added` | nova revisão de engenharia | `part_id`, `revision_code`, `spec_ref`, `drawing_ref` | — |
| `asset.part.revision_superseded` | supersessão registrada | `part_id`, `predecessor_revision`, `successor_revision`, `reason` | I‑PRT‑1 |
| `asset.part.lifecycle_state_changed` | ativa→superseded/obsolete/alternate | `part_id`, `from_state`, `to_state` | I‑PRT‑1 |
| `asset.part.interchangeability_group_changed` | membro entra/sai do grupo | `group_id`, `part_revision_ref`, `change` (`ADDED`/`REMOVED`) | I‑PRT‑2 |
| `asset.applicability.asserted` | aplicabilidade afirmada | `applicability_id`, `part_ref`, `part_revision_ref`, `target`, `evidence_ref` | I‑APP‑1 |
| `asset.applicability.withdrawn` | aplicabilidade revogada | `applicability_id`, `reason`, `correction_ref` | I‑APP‑2 |

### Inventory
| `asset.inventory.stock_position_opened` | primeira quantidade numa `(part, location, purpose)` | `stock_position_id`, `part_ref`, `location_ref`, `purpose`, `ownership` | I‑INV‑0 |
| `asset.inventory.stock_adjusted` | ajuste manual auditado | `stock_position_id`, `delta_by_status`, `reason`, `actor_ref` | I‑INV‑3 |
| `asset.inventory.stock_reserved` | reserva criada (HELD) | `reservation_id`, `stock_position_ref`, `demand`, `qty`, `purpose`, `priority`, `decision_ref?` | I‑INV‑1/2, I‑WO‑2 |
| `asset.inventory.stock_reservation_allocated` | HELD→ALLOCATED | `reservation_id` | — |
| `asset.inventory.stock_reservation_released` | reserva liberada | `reservation_id`, `reason` | I‑INV‑1 |
| `asset.inventory.stock_consumed` | ALLOCATED→CONSUMED (peça usada na WO) | `reservation_id`, `work_order_ref`, `qty`, `lot?`, `serial?` | I‑WO‑2 |
| `asset.inventory.allocation_decided` | disputa resolvida | `part_ref`, `location_ref`, `winning_demand`, `losing_demands`, `decision_ref` | I‑INV‑2 |
| `asset.inventory.transfer_requested` | transferência pedida | `transfer_id`, `part_ref`, `from_location_ref`, `to_location_ref`, `qty`, `linked_reservation_ref?` | I‑INV‑4 |
| `asset.inventory.transfer_dispatched` | saiu da origem | `transfer_id`, `qty`, `from_location_ref` | I‑INV‑4 |
| `asset.inventory.transfer_received` | chegou (total ou parcial) | `transfer_id`, `qty_received`, `to_location_ref`, `partial` (bool) | I‑INV‑4 |

### CustomerSite
| `asset.site.registered` | OM/site criado | `site_id`, `customer_ref`, `code`, `kind` | I‑SEC‑2 |

## 2. Módulo `sustainment`

### SLIContract
| `asset.sustainment.contract_registered` | contrato criado | `contract_id`, `customer_ref` | I‑SLI‑3 |
| `asset.sustainment.contract_version_issued` | nova versão (inicial ou por emenda) | `contract_id`, `version_no`, `effective`, `coverage_summary`, `amendment_ref?` | I‑SLI‑3 |

### Entitlement (resultado de decisão do Core, registrado no contexto da WO)
| `asset.sustainment.entitlement_resolved` | entitlement calculado para `(vehicle, part|service, instant)` | `vehicle_ref`, `subject` (part/service ref), `instant`, `decision_ref`, `outcome` (`GRANTED`/`DENIED`/`GRANTED_WITH_EXCEPTION`), `breakdown` | I‑SLI‑1/2/4/5 |

### WorkOrder
| `asset.sustainment.work_order_opened` | WO aberta | `work_order_id`, `vehicle_ref`, `site_ref`, `failure`, `contract_context` (congelado) | I‑SLI‑1 |
| `asset.sustainment.work_order_task_added` | tarefa adicionada | `work_order_id`, `task_id`, `mandatory` | I‑WO‑1 |
| `asset.sustainment.material_demanded` | demanda de material registrada | `work_order_id`, `task_id`, `part_ref`, `qty` | I‑WO‑2 |
| `asset.sustainment.material_reserved` | reserva vinculada à WO confirmada | `work_order_id`, `reservation_ref`, `part_ref`, `qty` | I‑WO‑2, I‑WO‑4 |
| `asset.sustainment.work_order_state_changed` | transição de estado da WO | `work_order_id`, `from_state`, `to_state`, `reason?` | I‑WO‑3/4 |
| `asset.sustainment.work_order_priority_recalculated` | score mudou | `work_order_id`, `score`, `breakdown`, `evaluation_ref` | I‑WO‑5 |
| `asset.sustainment.task_started` / `task_completed` | execução de tarefa | `work_order_id`, `task_id`, `labor_entry?` | I‑WO‑1 |
| `asset.sustainment.component_removed` | componente retirado | `work_order_id`, `part_ref`, `serial?`, `disposition` | I‑PRT‑1 |
| `asset.sustainment.work_order_technically_complete` | fim técnico | `work_order_id`, `diagnosis`, `root_cause`, `resolution` | I‑WO‑1 |
| `asset.sustainment.post_maintenance_validated` | validação executada | `work_order_id`, `validation_ref`, `result` | I‑WO‑1 |
| `asset.sustainment.work_order_completed` | WO fechada | `work_order_id`, `closed_at` | I‑WO‑1 |
| `asset.sustainment.work_order_cancelled` | WO cancelada | `work_order_id`, `from_state`, `reason` (obrigatório) | I‑WO‑3 |
| `asset.sustainment.failure_recorded` | falha registrada (leve; base para confiabilidade) | `work_order_id`, `vehicle_ref`, `mode`, `affected_position`, `observed_at` | constituição §19 |

## 3. Consumidores (dentro do slice)

| Evento | Consumidor | Efeito |
|---|---|---|
| `asset.inventory.stock_reserved` / `_released` / `_consumed`, `asset.inventory.transfer_received` | projeção `WorkshopDashboard`; recalculador de `WAITING_MATERIAL` da WO | reavaliar I‑WO‑4; atualizar breakdown de material |
| `asset.sustainment.work_order_state_changed` / `_priority_recalculated` | projeção `WorkshopDashboard`; projeção `FleetView` | reordenar fila; atualizar contagem de frota |
| `asset.vehicle.lifecycle_state_changed` | projeção `FleetView`; projeção de contrato (fora do slice) | disponível/degradado/indisponível |
| `asset.sustainment.failure_recorded` | (fora do slice) pipeline de confiabilidade | apenas capturado |
| todos | `event_log` do Core + cadeia de integridade + `checkpoint` | trilha imutável (I‑WO‑3, constituição §24) |

## 4. Regras de eventos

- **Sem estado de IA como fato** (constituição §23): `entitlement_resolved` e `priority_recalculated`
  carregam `decision_ref`/`evaluation_ref` do Core — são decisões governadas, não heurística.
- **Correção não destrói histórico** (constituição §24): eventos `*_corrected` / `*_withdrawn` /
  `*_cancelled` **acrescentam**; nunca há `UPDATE`/`DELETE` de evento.
- **Idempotência de entrega**: consumidores usam `core_application.inbox` + chave de idempotência.
- **Ordem**: a cadeia de integridade é por agregado (decisão F); consumidores não assumem ordem total entre
  agregados distintos — a garantia de ordem só vale dentro de um `aggregate_ref` (por `aggregate_version`).
- **Colisão de namespace**: teste de `MULTI_VERTICAL_CI_GATES.md` §7 garante que nenhum `message_type`
  `asset.*` colide com `livestock.*` nem tem dono duplo.
