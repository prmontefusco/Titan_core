# 07 — BUSINESS INVARIANTS — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Cada invariante: enunciado · escopo (agregado/transação) · camada de enforcement · **o que NUNCA pode
acontecer** (constituição §36) · teste de regressão. Autoridade: se a implementação conflita com um
invariante aceito, a implementação está errada (constituição §32).

Camadas: **D** = invariante de agregado no domínio (`*_domain`, `__post_init__`/factory); **A** = regra na
aplicação (`*_application`); **DB** = constraint/RLS/trigger na persistência; **GOV** = `Rule` governada +
`Decision` do Core.

---

## Veículo e configuração

### I‑VEH‑1 — Uma baseline efetiva por veículo em T
**Enunciado:** um `Vehicle` tem **exatamente uma** `ConfigurationBaseline` vigente no instante T.
**Escopo:** agregado `Vehicle` (`current_baseline_ref`) + seleção temporal.
**Camada:** D (a referência é única) + A (a troca de baseline é um comando auditado com `valid_from`).
**NUNCA:** um veículo sem baseline vigente após o registro; duas baselines "vigentes" simultâneas.
**Teste:** registrar veículo sem baseline → recusa; trocar baseline → a anterior ganha `valid_to`, a nova
`valid_from`; consulta em data passada retorna a baseline correta daquele instante.

### I‑VEH‑2 — Leitura de medidor é monotônica, correção não apaga
**Enunciado:** uma nova `MeterReading` de um `kind` é ≥ a última do mesmo `kind`, salvo `CorrectionEvent`
explícito; a leitura original permanece no histórico.
**Escopo:** agregado `Vehicle`.
**Camada:** D + DB (append‑only na tabela de leituras).
**NUNCA:** hodômetro/horímetro retroceder silenciosamente; uma leitura ser sobrescrita.
**Teste:** leitura menor que a anterior sem correção → recusa; com `CorrectionEvent` → aceita e ambas
constam.

### I‑VEH‑3 — Transição de ciclo de vida monotônica e auditada
**Enunciado:** `VehicleLifecycleState` só muda por transição permitida, com ator, autorização, evento e
registro de auditoria; `IN_MAINTENANCE`↔`AVAILABLE` só via WO (`ReturnToService` exige
`PostMaintenanceValidation`).
**Escopo:** agregado `Vehicle` + coordenação com `WorkOrder`.
**Camada:** D (tabela de transições) + A + GOV (autorização).
**NUNCA:** veículo sair de `IN_MAINTENANCE` para `AVAILABLE` sem WO validada.
**Teste:** `ReturnToService` sem `validation` → recusa; transição não listada → recusa com motivo.

### I‑CFG‑1 — Cadeia de revisão de configuração acíclica
**Enunciado:** `ConfigurationRevision.supersedes_ref` nunca forma ciclo.
**Escopo:** agregado `ConfigurationBaseline`.
**Camada:** D (`__post_init__` valida) + DB (FK auto‑referenciada + `UNIQUE` na sucessora).
**NUNCA:** A supersede B e B supersede A (direta ou transitivamente).
**Teste:** tentar fechar ciclo → `RevisãoCíclica`.

### I‑CFG‑2 — Efetividade não sobrepõe para a mesma posição
**Enunciado:** para uma dada `position_code`, os intervalos de `Effectivity` (série × data) de baselines
ativas **não se sobrepõem**.
**Escopo:** consulta cross‑agregado por modelo/variante.
**Camada:** A (validação na publicação de baseline) + teste de propriedade.
**NUNCA:** duas baselines ativas responderem "sou a config desta posição" para o mesmo `(serial, data)`.
**Teste:** publicar baseline com faixa que sobrepõe outra ativa na mesma posição → recusa.

## Peça e aplicabilidade

### I‑PRT‑1 — Supersessão de peça acíclica; instalação histórica preservada
**Enunciado:** o grafo de `Supersession` entre `PartRevision` é acíclico; superseção **não** altera nem
remove registros de instalações passadas (cenário D).
**Escopo:** agregado `Part` + histórico de `BaselinePosition`/consumo.
**Camada:** D (aciclicidade) + DB (append‑only de instalações) + A.
**NUNCA:** ao superseder uma revisão, uma `ConfigurationBaseline` histórica passar a "apontar" para a nova.
**Teste:** superseder rev. 2→3; baseline as‑maintained de 2026‑01 continua mostrando rev. 2; planejamento
de nova manutenção passa a propor rev. 3 **se aplicável**.

### I‑PRT‑2 — Intercambiabilidade simétrica
**Enunciado:** se X ∈ grupo G e Y ∈ grupo G, então X substitui Y **e** Y substitui X sob as condições de G.
**Escopo:** agregado `InterchangeabilityGroup`.
**Camada:** D (a pertinência é bidirecional por construção).
**NUNCA:** "X pode virar Y" sem "Y pode virar X" dentro do mesmo grupo.
**Teste:** consultar substitutos de X e de Y no grupo → conjuntos coerentes e simétricos.

### I‑APP‑1 — Aplicabilidade só existe com evidência
**Enunciado:** toda `Applicability` no estado `ASSERTED` tem `evidence_ref` não nulo apontando para um
`Evidence` do Core; não existe aplicabilidade "booleana".
**Escopo:** agregado `Applicability`.
**Camada:** D (`__post_init__`) + DB (`NOT NULL` + FK) — fail closed (constituição §11, §42).
**NUNCA:** o sistema responder "peça serve no veículo" sem uma asserção datada com evidência.
**Teste:** criar `Applicability` sem evidência → recusa; consulta de aplicabilidade retorna a asserção +
`evidence_ref`, nunca só `true`.

### I‑APP‑2 — Retirada de aplicabilidade por correção, não por delete
**Enunciado:** revogar uma `Applicability` gera estado `WITHDRAWN` + `CorrectionEvent`; o registro
`ASSERTED` original permanece.
**Camada:** D + DB (append‑only).
**NUNCA:** `DELETE` de uma aplicabilidade que já foi usada por uma decisão/instalação.
**Teste:** revogar aplicabilidade usada em WO fechada → histórico da WO intacto; nova consulta não a retorna.

## Inventário

### I‑INV‑0 — Peça sem estoque implícito
**Enunciado:** criar um `Part` **não** cria nenhuma `StockPosition`.
**Camada:** D/A (agregados separados).
**NUNCA:** assumir `available > 0` porque a peça existe.
**Teste:** `Part` recém‑criado → `available` em qualquer localização = 0, com breakdown vazio.

### I‑INV‑1 — Disponível ≥ 0 e derivado, nunca armazenado como booleano
**Enunciado:** `available(part, location, purpose) = on_hand − Σ reservas_ativas − quarantine − inspection −
damaged ≥ 0`, calculado a cada leitura; a resposta inclui o `AvailabilityBreakdown`.
**Escopo:** agregado `StockPosition` (+ `StockReservation` ativas).
**Camada:** D (a soma nunca fica negativa; comando que a levaria a <0 é recusado) + A (breakdown na
resposta).
**NUNCA:** `is_available: true` persistido; `available` negativo; consumir quantidade indisponível
(constituição §36).
**Teste:** reservar mais que `available` → recusa; concorrência: duas reservas simultâneas somando > `on_hand`
→ uma falha por `OptimisticConcurrencyConflict`/lock, `available` final ≥ 0.

### I‑INV‑2 — Disputa de estoque resolve por decisão explicável e auditável
**Enunciado:** quando `PRODUCTION`, `SERVICE_SLI` e `COMMERCIAL` concorrem pela mesma peça física, a
alocação é decidida por política de reserva/prioridade e produz um `Decision` do Core com o porquê
(cenário C); a quantidade total **não** é simplesmente reportada.
**Escopo:** `StockReservation` + `Decision`.
**Camada:** GOV (`Rule` de política de alocação governada) + A.
**NUNCA:** estoque reservado/protegido por contrato ser tomado por outro propósito sem `Decision`
registrando a autorização (constituição §36).
**Teste:** cenário C — três demandas, `on_hand` insuficiente; a que perde recebe recusa com `decision_ref`
explicando (`−prioridade menor`, `−propósito não autorizado a consumir SERVICE_SLI`).

### I‑INV‑3 — Inventário só muda sob transação com concorrência controlada
**Enunciado:** toda alteração de `StockQuantities`/reservas ocorre em transação com `version` check +
`SELECT ... FOR UPDATE` das posições afetadas; ajustes manuais geram `StockAdjustment` auditado.
**Camada:** DB + A.
**NUNCA:** perder quantidade em transferências concorrentes; ajuste sem trilha (constituição §42).
**Teste:** transferência A→B e reserva em A simultâneas → soma conservada; `StockAdjustment` sempre com
ator, motivo e evento.

### I‑INV‑4 — Transferência conserva quantidade; recebimento ≤ despachado
**Enunciado:** `Σ recebido(transfer) ≤ qty_despachada`; enquanto `IN_TRANSIT`, a quantidade não está
`ON_HAND` em nenhuma ponta; custódia referenciada em `core_domain.provenance` sem buraco temporal.
**Camada:** D + A.
**NUNCA:** a mesma unidade contar como disponível na origem e no destino ao mesmo tempo.
**Teste:** cenário B — despacho 5, recebimento parcial 3 → origem −5, trânsito 2, destino +3; tentar
receber 3 (total 6) → recusa.

## Contrato SLI e entitlement

### I‑SLI‑1 — Uma linha de contrato ativa por serviço, congelada no instante
**Enunciado:** uma `WorkOrder` resolve, na abertura, para **exatamente uma** `ContractVersion` +
`CoverageLine` ativa naquele instante; esse `ContractContext` é **congelado** na WO.
**Escopo:** agregado `WorkOrder` (VO `ContractContext`) + seleção temporal em `SLIContract`.
**Camada:** A (resolução na abertura) + D (VO imutável) + GOV (a resolução é uma `Evaluation`).
**NUNCA:** avaliar/faturar uma WO histórica com a versão de contrato de hoje (cenário E).
**Teste:** abrir WO sob versão A; emendar contrato para B antes do fechamento; o dossiê da WO cita A em
todos os eventos anteriores à emenda.

### I‑SLI‑2 — Seleção temporal de versão precede qualquer avaliação de cobertura
**Enunciado:** a versão do contrato é escolhida por tempo válido **e** tempo de conhecimento
(`shared_kernel.temporal`) **antes** de qualquer regra de elegibilidade rodar (padrão ADR‑0061 do Core).
**Camada:** A + GOV.
**NUNCA:** rodar regra de cobertura contra um agregado de versão indefinida.
**Teste:** consulta de entitlement em data D usa a versão vigente em D, não a `current_version_no`.

### I‑SLI‑3 — `ContractVersion` imutável após emissão
**Enunciado:** uma `ContractVersion` emitida não é editada; correção = nova versão via
`ContractAmendment`.
**Camada:** DB (append‑only) + D.
**NUNCA:** `UPDATE` em `coverage_lines`/`SLA` de uma versão já referenciada por alguma WO.
**Teste:** editar versão referenciada → recusa; emenda cria `version_no + 1` com `amendment_ref`.

### I‑SLI‑4 — Entitlement é `Decision` do Core, não `if`
**Enunciado:** o direito a peça/serviço é o resultado de `Evaluation → Decision` governada do Core, com
fatos tipados e `context_hash`; nunca lógica ad hoc em `work_order_service`.
**Escopo:** `sustainment_application` + `core_domain.{rule,evaluation,decision,decision_governance}`.
**Camada:** GOV.
**NUNCA:** um `Decision` de IA/heurística virar fato transacional (constituição §23); entitlement decidido
por código não governado.
**Teste:** `grep` no `packages/sustainment_*` não acha lógica de cobertura fora de `Rule`/`Evaluation`; o
entitlement retornado tem `decision_ref` com breakdown.

### I‑SLI‑5 — Entitlement não excede a cobertura contratada
**Enunciado:** a soma dos entitlements concedidos para um limite de serviço/período ≤ o teto da
`CoverageLine`/`ServiceLimits`.
**Camada:** GOV + A (leitura dos limites consumidos como fato).
**NUNCA:** conceder além do contratado sem uma `Decision` de exceção explícita e autorizada.
**Teste:** consumir o teto; próxima concessão recusada com `−limite de serviço atingido`.

## Work Order

### I‑WO‑1 — Não fecha com obrigação aberta nem sem validação
**Enunciado:** `WorkOrder` só chega a `COMPLETED` se toda `WorkTask.mandatory` está `DONE` e
`PostMaintenanceValidation` existe e passou.
**Escopo:** agregado `WorkOrder`.
**Camada:** D (guarda de transição).
**NUNCA:** fechar manutenção sem validação obrigatória (constituição §36).
**Teste:** `CloseWorkOrder` com tarefa obrigatória `OPEN` → recusa; sem `validation` → recusa.

### I‑WO‑2 — Material reservado ≤ material demandado
**Enunciado:** para cada `MaterialDemand`, `Σ StockReservation.qty (HELD|ALLOCATED|CONSUMED) ≤ demand.qty`.
**Escopo:** agregado `WorkOrder` (referências) + `StockReservation`.
**Camada:** A (ao criar reserva a partir da demanda) + D.
**NUNCA:** reservar/consumir para uma WO mais do que ela demandou.
**Teste:** demanda 2, reservar 3 → recusa; consumir 2 → demanda satisfeita, terceira reserva impossível.

### I‑WO‑3 — Toda transição de estado emite evento + auditoria
**Enunciado:** cada mudança de `WorkOrderState`/`WorkTask.state` produz um evento de domínio append‑only e
um registro de auditoria; motivo obrigatório em `CANCELLED`, `INTERRUPTED`, `WAITING_AUTHORIZATION`.
**Camada:** A + DB (event_log do Core).
**NUNCA:** estado mudar sem rastro; `CANCELLED` sem motivo.
**Teste:** cada transição gera exatamente um evento com ator, timestamp, origem, destino; `CANCELLED` sem
motivo → recusa.

### I‑WO‑4 — `WAITING_MATERIAL` é derivado, não decorativo
**Enunciado:** a WO entra em `WAITING_MATERIAL` **sse e somente se** existe `MaterialDemand` com
`Σ reservado < qty` e sem estoque atendível na localização da oficina; sai quando a condição deixa de valer
(pós‑transferência/recebimento — cenário B).
**Camada:** A (projeção da condição a cada evento de reserva/recebimento).
**NUNCA:** WO "pronta" com material faltando; WO presa em `WAITING_MATERIAL` após o material chegar.
**Teste:** cenário B ponta a ponta — abertura → `WAITING_MATERIAL` → transferência → recebimento → reserva
→ `READY`.

### I‑WO‑5 — `PriorityScore` determinístico e explicável
**Enunciado:** o score é função pura dos fatores + pesos de uma `Rule` versionada; a mesma entrada produz o
mesmo score; a resposta carrega o breakdown e `evaluation_ref`.
**Camada:** GOV + D.
**NUNCA:** score de IA/oculto para prioridade operacional (constituição §22).
**Teste:** dois cálculos com a mesma entrada → score idêntico; mudar o peso exige nova versão da `Rule`;
a UI consegue explicar por que WO‑1 vem antes de WO‑2.

## Tenant e escopo

### I‑SEC‑1 — Isolamento por Organization (RLS)
**Enunciado:** todo agregado tem `organization_id`; RLS por `titan.organization_id` sob role restrita
(`NOLOGIN NOSUPERUSER NOBYPASSRLS`); FKs compostas por Organization (ADR‑0077).
**Camada:** DB (RLS) + A (`OrganizationContext`).
**NUNCA:** expor dado de outra Organization; `titan` superusuário mascarar a falha no teste (usar role
temporário — `CLAUDE.md` "Armadilhas do ambiente").
**Teste:** padrão de `tests/integration/test_organization_postgresql.py` para cada tabela nova.

### I‑SEC‑2 — Escopo OM/Site aplicado antes da divulgação (decisão G)
**Enunciado:** um principal com escopo da OM A não lê veículos/contratos/estoque/WO da OM B **dentro da
mesma Organization operadora**; a autorização acontece **antes** da resolução do dado (constituição §26).
**Camada:** A (predicado de `site_scope` no `OrganizationContext` estendido da vertical) + DB (predicado de
consulta por `site_id`) + GOV (política de acesso por site).
**NUNCA:** um `SELECT` amplo por Organization vazar OMs não autorizadas ao chamador.
**Teste:** sob role restrita, principal com `site_scope = {A}` consulta frota → só veículos de A; tenta WO
de B → 404 sem vazar existência. Ver `11_AUTHORIZATION_MODEL.md`.

---

## Matriz invariante × cenário da constituição §41

| Cenário | Invariantes exercidos |
|---|---|
| A (estoque local) | I‑SLI‑1/4, I‑INV‑1, I‑WO‑1/2/3, I‑VEH‑3, I‑SEC‑1/2 |
| B (sem estoque local) | I‑INV‑4, I‑WO‑4, I‑INV‑1/3, I‑SLI‑1 |
| C (disputa produção×SLI×venda) | I‑INV‑2, I‑INV‑1, I‑SLI‑5 |
| D (supersessão) | I‑PRT‑1, I‑APP‑2, I‑CFG‑1 |
| E (contrato expira com WO aberta) | I‑SLI‑1/2/3, I‑WO‑3 |
| F (catálogo 3D) | I‑APP‑1 (frontend não decide aplicabilidade) |
