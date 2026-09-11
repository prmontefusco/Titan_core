# 06 — AGGREGATE ANALYSIS — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Deriva de `05_DOMAIN_MODEL.md`. **Nem todo substantivo é agregado** (constituição §40). Fronteira de
agregado = **menor unidade que precisa ser transacionalmente consistente para manter um invariante**.
Entre agregados: referência por id, consistência eventual, concorrência otimista por agregado.

---

## 1. Agregados propostos

| Agregado (raiz) | Por que é um agregado (invariante que exige consistência forte) | Fronteira (o que está dentro) | Referências externas (por id) |
|---|---|---|---|
| **Vehicle** | 1 baseline efetiva em T; ciclo de vida monotônico; meter reading não retrocede | `Vehicle` + `MeterReading[]` (VO append‑only) + `lifecycle_state` | `ConfigurationBaseline`, `CustomerSite`, `VehicleModel/Variant`, `SLIContract` |
| **ConfigurationBaseline** | cadeia de revisão acíclica; efetividade não sobrepõe para a mesma posição | `ConfigurationBaseline` + `ConfigurationRevision` (VO) + `BaselinePosition[]` (VO) + `Effectivity` (VO) | `Part`, `PartRevision`, `VehicleModel/Variant` |
| **Part** | supersessão acíclica entre revisões; estado de ciclo de vida coerente com a cadeia | `Part` + `PartRevision[]` (E interna) + `Supersession[]` (VO) | `InterchangeabilityGroup`, `Evidence` (spec/drawing refs) |
| **Applicability** | uma asserção tem **exatamente uma** evidência obrigatória; retirada só por correção | `Applicability` (raiz própria — **não** é parte de `Part`, porque muda em cadência e por atores diferentes) | `Part`, `PartRevision`, `Evidence` |
| **InterchangeabilityGroup** | pertinência **simétrica**: adicionar/remover membro mantém a simetria | `InterchangeabilityGroup` + `member_part_revisions[]` | `PartRevision` |
| **StockPosition** | `available(purpose) ≥ 0`; nenhuma linha de reserva excede `on_hand` menos os demais status | `StockPosition` + `StockQuantities` (VO) + `StockReservationLine[]` (VO — projeção das reservas ativas) | `Part`, `StockLocation`, `StockReservation` |
| **StockReservation** | transição de estado válida (`HELD→ALLOCATED→CONSUMED`/`RELEASED`); disputa resolvida por decisão explicável | `StockReservation` + `state` + `decision_ref` | `StockPosition`, `Decision`, demanda (`WorkOrder`/…) |
| **StockTransfer** | quantidade em trânsito conservada; recebimento (parcial) nunca excede o despachado | `StockTransfer` + `state` + linhas de recebimento | `Part`, `StockLocation` (from/to), `StockReservation` |
| **SLIContract** | versões monotônicas e **imutáveis** após emissão; no máximo uma versão vigente em T | `SLIContract` + `ContractVersion[]` (E interna append‑only) + `CoverageLine[]`/`SLA` (VO) | `Customer`, `ContractAmendment` |
| **WorkOrder** | não fecha com tarefa obrigatória aberta; reservado ≤ demandado; toda transição = evento+auditoria; contexto contratual congelado na abertura | `WorkOrder` + `WorkTask[]` (E interna) + `MaterialDemand[]` (VO) + `ContractContext` (VO congelado) + `FailureRecord` (VO) + `validation` (VO) | `Vehicle`, `CustomerSite`, `Workshop`, `SLIContract`+version_no, `StockReservation` |
| **CustomerSite** | identidade estável de OM/site; escopo de autorização | `CustomerSite` + `contacts` (VO) | `Customer`, `Organization` |

## 2. Substantivos que **não** são agregados

| Substantivo | O que é | Onde vive |
|---|---|---|
| `MeterReading` | VO append‑only dentro de `Vehicle` | agregado `Vehicle` |
| `PartRevision` | entidade **interna** de `Part` (não tem ciclo de vida independente da peça) | agregado `Part` |
| `ContractVersion` | entidade **interna** de `SLIContract` | agregado `SLIContract` |
| `WorkTask` | entidade **interna** de `WorkOrder` | agregado `WorkOrder` |
| `MaterialDemand` | VO de `WorkOrder` | agregado `WorkOrder` |
| `Entitlement` | **não é persistido como verdade** — é o `Decision` do Core + projeção de leitura | Core (`Decision`) + read model |
| `WorkshopDashboard` | **read model / projeção** | `sustainment_application` + repo de leitura |
| `FleetView` | **read model / projeção** | `asset_application` + repo de leitura (`05` §2.6) |
| `PriorityScore` | VO calculado (com `evaluation_ref`) | dentro de `WorkOrder` / projeção do dashboard |
| `FailureRecord` | VO leve dentro de `WorkOrder` no slice (vira agregado próprio quando confiabilidade entrar — constituição §19) | agregado `WorkOrder` |
| `StockLocation` | entidade de referência (CRUD), sem invariante transacional forte | tabela simples |
| `AvailabilityBreakdown` | VO de resposta (derivação de `StockPosition`) | calculado on‑read |

## 3. Fronteiras que **quase** foram desenhadas erradas

| Tentação | Por que está errada | Decisão |
|---|---|---|
| `Applicability` como campo/coleção de `Part` | aplicabilidade muda por engenharia/configuração numa cadência e por atores diferentes do catálogo da peça; acoplar infla o agregado `Part` e serializa edições não relacionadas | `Applicability` é **agregado próprio** que referencia `Part` por id |
| `StockReservation` como entidade interna de `StockPosition` | a reserva tem ciclo de vida próprio, é criada por outra transação (demanda da WO) e, no cenário B, é **assíncrona** (pós‑transferência) | `StockReservation` é **agregado próprio**; `StockPosition` guarda só a **projeção** das linhas ativas para calcular `available` |
| `WorkOrder` engolir `StockReservation` (reserva na mesma transação sempre) | cenário B: material vem de outra localização, a reserva acontece **depois** do recebimento; forçar tudo numa transação impede o fluxo | no cenário A (estoque local) a reserva **pode** entrar na mesma transação como **operação coordenada** entre `sustainment` e `asset`; no cenário B vira fluxo próprio com evento. A `WorkOrder` referencia `StockReservation` por id em ambos |
| `WorkOrder` como "God Aggregate" com contrato, veículo e estoque dentro | viola constituição §15; acopla três bounded contexts | `WorkOrder` **congela** um `ContractContext` (VO) na abertura e **referencia** `Vehicle`/`StockReservation` por id |
| `ContractVersion` mutável | cenário E: reavaliar WO histórica com a definição de hoje | `ContractVersion` **imutável** após emissão; emenda cria nova versão |
| `Entitlement` como tabela de verdade da vertical | duplicaria a lógica de decisão do Core e permitiria divergência | `Entitlement` = `Evaluation → Decision` do Core, anexado ao evento da WO |

## 4. Concorrência e transação (constituição §29, §36)

- **Concorrência otimista por agregado**: `version: int` em `Vehicle`, `ConfigurationBaseline`, `Part`,
  `Applicability`, `StockPosition`, `StockReservation`, `StockTransfer`, `SLIContract`, `WorkOrder`. Conflito
  → `OptimisticConcurrencyConflict` do Core.
- **`StockPosition` também exige controle pessimista pontual** onde há disputa: `SELECT ... FOR UPDATE` da(s)
  posição(ões) alvo antes de calcular `available` e gravar a reserva (padrão de
  `livestock_infrastructure` `transformation_locking.py`), para não perder inventário em transferências
  concorrentes (constituição §36: "não perder inventário durante transferências concorrentes").
- **Uma unidade de trabalho = uma vertical** (`MULTI_VERTICAL_CI_GATES.md` §8). A operação "abrir WO +
  reservar material local" toca `sustainment` **e** `asset`: no B1 (mesma vertical) isso é aceitável dentro
  de uma transação; a fronteira externa continua sendo `asset` ⊥ `livestock`. Se B2 (irmãs), a reserva vira
  **saga por evento** e a WO entra em `WAITING_MATERIAL` até o `MaterialReserved`.
- **Idempotência** (`core_application.idempotency`) em todo comando com efeito colateral externo (reservar,
  transferir, consumir, fechar).

## 5. Eventos por agregado → `08_DOMAIN_EVENTS.md`; comandos → `09_COMMAND_MODEL.md`.

## 6. Candidatos a revisão em A1 (com o negócio)

- `Applicability`: agregado próprio **ou** entidade interna de `PartRevision`? (depende da cadência real de
  mudança de aplicabilidade vs revisão).
- `Vehicle` vs `ConfigurationBaseline`: um agregado só ("veículo carrega sua baseline") **ou** dois? Proposta
  = dois, ligados por `current_baseline_ref`, porque a baseline é modelo‑nível e reusada por muitos veículos.
- `StockPosition` granularidade: por `(part, location, purpose)` **ou** também por `lot`/`serial` desde o
  slice? Proposta = incluir `lot`/`serial` opcionais já, para não migrar depois.
