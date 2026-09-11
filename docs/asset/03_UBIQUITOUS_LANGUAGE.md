# 03 — UBIQUITOUS LANGUAGE — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Vocabulário do domínio, a ser usado idêntico em código, testes, API (na camada de apresentação) e conversa.
Termo militar fica na camada de aplicação/apresentação; o núcleo usa o conceito genérico quando possível
(constituição §18). Onde o Titan Core já tem o conceito, **reusa‑se o nome do Core** — não se cria sinônimo.

Convenções: **PT** = termo de negócio; **EN** = identificador em código; *(Core)* = vem de
`packages/core_*` e não é redefinido aqui.

---

## 1. Ativo e configuração

| PT | EN | Definição |
|---|---|---|
| Veículo | `Vehicle` | Ativo técnico configurável, identificado por série/chassi/frota. Não é item de estoque. |
| Modelo de veículo | `VehicleModel` | Dado, não código. Define a família a que baselines e aplicabilidades se referem. |
| Variante | `VehicleVariant` | Subdivisão de um modelo. |
| Número de série / chassi / frota | `SerialNumber` / `Chassis` / `FleetNumber` | Identificadores externos do veículo. |
| Configuração‑base | `ConfigurationBaseline` | Conjunto vigente de posições e revisões que descreve **como o veículo está montado** num intervalo de efetividade. |
| Revisão de configuração | `ConfigurationRevision` | Versão de uma baseline; cadeia acíclica de supersessão. |
| Efetividade | `Effectivity` | Intervalo (modelo/variante/faixa de série/data) em que uma baseline/aplicabilidade vale. |
| Estado de ciclo de vida (veículo) | `VehicleLifecycleState` | `AVAILABLE`, `DEGRADED`, `MAINTENANCE_PLANNED`, `IN_MAINTENANCE`, `UNAVAILABLE`, `WAITING_MATERIAL` (derivado). Transição monotônica e auditável. |
| Leitura de medidor | `MeterReading` | Horímetro/hodômetro; append‑only; não retrocede sem correção. |
| As‑designed / as‑built / as‑delivered / as‑maintained | `ConfigurationView` | Perspectivas temporais da configuração de um veículo. |
| Posição | `Position` | Ponto na estrutura do veículo onde um componente/peça se instala. |

## 2. Peça (Part Master)

| PT | EN | Definição |
|---|---|---|
| Peça | `Part` | Objeto técnico: part number, descrição, fabricante, PN do fabricante, NSN opcional, classificações externas. |
| Revisão de peça | `PartRevision` | Versão de engenharia de uma peça; especificação, desenho, materiais, tolerâncias. |
| Supersessão | `Supersession` | Relação "esta revisão substitui aquela"; cadeia **acíclica**. |
| Predecessora / sucessora | `Predecessor` / `Successor` | Extremos de uma supersessão. |
| Peça alternativa | `AlternatePart` | Peça que atende a mesma função sob condições declaradas. |
| Grupo de intercambiabilidade | `InterchangeabilityGroup` | Conjunto onde a substituição é **simétrica**. |
| Aplicabilidade | `Applicability` | Asserção **datada e com evidência** de que uma peça/revisão serve a um modelo/configuração/faixa de série/data. Nunca um booleano. |
| Evidência de aplicabilidade | `ApplicabilityEvidence` *(usa `core_domain.evidence`)* | O que sustenta a asserção (documento, decisão de engenharia). |
| Estado de ciclo de vida (peça) | `PartLifecycleState` | `ACTIVE`, `SUPERSEDED`, `OBSOLETE`, `ALTERNATE`. |
| Número de peça do fabricante | `ManufacturerPartNumber` | — |
| NSN | `NatoStockNumber` | Quando aplicável ao domínio. |

## 3. Inventário e logística

| PT | EN | Definição |
|---|---|---|
| Localização de estoque | `StockLocation` | Armazém / bin / oficina / estoque de OM. Nó da rede de inventário. |
| Propósito de estoque | `StockPurpose` | `PRODUCTION`, `SERVICE_SLI`, `OM_REMOTE`, `COMMERCIAL`. Mesmo armazém físico, obrigações de negócio distintas (constituição §11). |
| Posição de estoque | `StockPosition` | Quantidades de uma peça em `(localização, propósito, status)`, opcionalmente por lote/série/dono. |
| Status de estoque | `StockStatus` | `ON_HAND`, `RESERVED`, `ALLOCATED`, `IN_TRANSIT`, `QUARANTINE`, `INSPECTION`, `DAMAGED`. |
| Dono do estoque | `StockOwnership` | `COMPANY_OWNED`, `CUSTOMER_OWNED`, `CONSIGNMENT`. |
| Em mãos | `on_hand` | Quantidade física presente. |
| Reservado | `reserved` | Comprometido a uma demanda específica; não disponível a outras. |
| Alocado | `allocated` | Reservado e destinado a uma execução concreta. |
| Disponível para prometer | `available` | `on_hand − reserved − quarantine − inspection − damaged`, **por propósito**. Sempre ≥ 0. |
| Reserva de estoque | `StockReservation` | Vínculo entre uma demanda (ex.: Work Order) e quantidade de uma `StockPosition`, com propósito e prioridade. |
| Transferência de estoque | `StockTransfer` | Movimento entre localizações; passa por `IN_TRANSIT` e recebimento (cenário B). |
| Recebimento | `Receiving` | Baixa do trânsito e entrada em `ON_HAND` na localização destino; pode ser parcial. |
| Ajuste de estoque | `StockAdjustment` | Correção de quantidade com auditoria (constituição §24). |
| Quarentena | `quarantine` | Retido, indisponível, aguardando decisão. |
| Componente reparável / retorno de núcleo | `RepairableComponent` / `CoreReturn` | Nomeado; fora do slice. |

## 4. Contrato SLI / Sustentação

| PT | EN | Definição |
|---|---|---|
| Contrato SLI | `SLIContract` | Acordo de suporte logístico integrado com um cliente. Bounded context de primeira classe. |
| Versão do contrato | `ContractVersion` | Estado versionado das regras contratuais num intervalo; emendas geram nova versão. |
| Linha de cobertura | `CoverageLine` | Regra que diz o que está coberto (modelo/veículo/OM/serviço/peça) numa `ContractVersion`. |
| Escopo geográfico | `GeographicScope` | OMs/regiões cobertas. |
| SLA de resposta / de reparo | `ResponseSLA` / `RepairSLA` | Prazos contratuais medidos a partir de eventos da Work Order. |
| Meta de disponibilidade | `AvailabilityTarget` | Percentual de frota disponível que o contrato exige (medição fora do slice). |
| Peça coberta / excluída | `CoveredPart` / `ExcludedPart` | — |
| Entitlement | `Entitlement` | Direito, derivado de contrato, a um serviço/peça específico para um veículo num instante. **É uma `Evaluation → Decision` governada do Core**, não um `if`. |
| Emenda contratual | `ContractAmendment` | Evento que produz nova `ContractVersion`. |

## 5. Manutenção / Work Order

| PT | EN | Definição |
|---|---|---|
| Solicitação de serviço | `ServiceRequest` | Origem de uma necessidade de manutenção (nomeado; no slice a WO pode nascer direto de uma falha). |
| Ordem de serviço | `WorkOrder` | Agregado transacional central da manutenção. Não é "God Aggregate". |
| Tarefa | `WorkTask` | Unidade de trabalho dentro de uma WO; pode ser obrigatória. |
| Demanda de material | `MaterialDemand` | Quantidade de uma peça que uma WO/tarefa precisa. |
| Reserva de material (da WO) | `WorkOrderMaterialReservation` | `StockReservation` cuja demanda é uma WO. |
| Falha | `FailureRecord` | Registro leve do modo de falha observado que originou/contextualiza a WO. |
| Diagnóstico / Causa / Resolução | `Diagnosis` / `RootCause` / `Resolution` | Campos do fechamento técnico. |
| Disposição do componente removido | `RemovedComponentDisposition` | O que aconteceu com a peça retirada (scrap, reparo, devolução, quarentena). |
| Validação pós‑manutenção | `PostMaintenanceValidation` | Verificação obrigatória antes do retorno ao serviço. |
| Estado da Work Order | `WorkOrderState` | Máquina de estados a **derivar** (candidatos em `05`/constituição §16). |
| Retorno ao serviço | `ReturnToService` | Transição do veículo de `IN_MAINTENANCE` para `AVAILABLE`. |
| Score de prioridade | `PriorityScore` | Número 0..100 **determinístico e explicável**, com os fatores que o compõem (constituição §22). Sem IA. |

## 6. Organização e site

| PT | EN | Definição |
|---|---|---|
| Organização | `Organization` *(Core)* | Tenant. Fronteira de isolamento (RLS, ADR‑0002/0003). |
| Contexto de organização | `OrganizationContext` *(Core)* | Principal autenticado + Organization + permissões. |
| Cliente | `Customer` | Parte contratante do SLI (pode ser a própria operadora ou externo). |
| OM / Site | `CustomerSite` | Unidade física do cliente: veículos, estoque local, oficina, contatos. Escopo de autorização — ver `11_AUTHORIZATION_MODEL.md` (decisão G). |
| Oficina | `Workshop` | Local onde Work Orders são executadas; associada a um `CustomerSite` ou à operadora. |

## 7. Conceitos do Core reutilizados sem redefinição

`Evaluation`, `Decision`, `DecisionGovernance`, `Policy`, `Rule`, `Normative` *(entitlement de SLI e
elegibilidade de garantia)*; `Evidence`, `Fact`, `Provenance`, `Relation` *(custódia de peça/lote/
shipment)*; `Correction`, `Supersession` *(a mecânica; a semântica de peça é da vertical)*; `Dossier` /
`VerificationBundle` com `VerticalSection` (ADR‑0060) *(dossiê de sustainment para auditoria contratual)*;
`event_log`, cadeia de integridade, `checkpoint`; `outbox`/`inbox`, `idempotency`,
`OptimisticConcurrencyConflict`; `shared_kernel` (`TypedId`, `UniversalReference`, `temporal`,
serialização canônica). Ver `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §3.

## 8. Termos proibidos no núcleo

`OM`, `MilitaryOrganization`, `Vehicle`, `Workshop`, `Part` **não entram em `packages/core_*` nem em
`shared_kernel`** (constituição §18, §42; `DEPENDENCY_RULES.md`). No Core, se algo genérico for necessário,
é `Scope`/`Site` abstrato via `CORE_CHANGE_REQUEST`.
