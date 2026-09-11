# SPEC — Titan Asset & Sustainment: primeiro slice (Vehicle→Work Order→Reserva de material→Dashboard de oficina)

- **Nível:** CRITICAL (tenancy, auditoria, integridade, entidades novas, API, migration, arquitetura de vertical)
- **Estado:** proposta
- **Decisão de Discovery:** PROCEED (condicionada às decisões A, F, G — ver §"Riscos, alternativas e perguntas abertas")
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-09-10
- **Vertical / lane:** `asset` (`vertical/asset/*`)
- **ADR:** `docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md` (rascunho)
- **Discovery:** `docs/asset/01`…`09`, `11`, `19`, `20`

---

## Problema e usuário

Um veículo sob contrato de sustentação (SLI) desenvolve uma necessidade de manutenção. Hoje o Titan não tem
como representar o ativo, sua configuração, a peça aplicável, o estoque real por propósito, o contrato
vigente à época, nem a ordem de serviço com prioridade explicável. Sem isso, oficina, logística e gestão de
contrato operam por planilha e não conseguem responder, com evidência, o que fazer a seguir e por quê.

Afetados: técnico de oficina, planejador, logístico, gestor de contrato SLI, engenharia, representante da OM
(`docs/asset/11_AUTHORIZATION_MODEL.md` §1).

Evidência de que vale resolver: a constituição multi‑agente define este marco (§46–§47); a Fase 0
(`docs/asset/CORE_REUSE_ASSESSMENT.md`) confirma que o Core já fornece identidade, autorização,
evento append‑only, integridade, outbox, política/regra/avaliação/decisão explicável e dossiê — a vertical
só precisa do domínio de Asset.

## Contexto e objetivo

Pertence ao Titan agora porque é o **primeiro slice vertical** de Asset & Sustainment e existe para **provar
que as fronteiras estão certas**, não para entregar toda a plataforma (constituição §46). Resultado
observável: um teste ponta a ponta (cenários A e B da constituição §41) em que o Titan responde, **com
evidência para cada resposta**, os 16 pontos do §47 (ver §"Critérios de aceite").

Corte do slice: **Vehicle + Part + Configuration + StockLocation + Inventory + SLI Contract + Work Order +
Material Reservation + Workshop Dashboard**.

## Fora de escopo

- Planejamento de manufatura, BOM explosion, kitting, line supply (constituição §13).
- Procurement (a demanda de material **para** em "falta detectada" — constituição §14).
- Catálogo 3D interativo / AR — só fronteira/adapter (constituição §9–§10).
- Analytics de confiabilidade (MTBF/MTTR) — só captura de `FailureRecord` (constituição §19).
- Manutenção preventiva/inspeção/campanha/retrofit, `MaintenancePlan`, agendamento de recursos.
- Rede logística completa (replenishment/reorder point/safety stock/cycle counting — constituição §12).
- Penalidades/créditos financeiros, relatórios contratuais, cálculo de disponibilidade agregada da frota.
- Integração ERP/PLM/WMS (o contrato de integração é propriedade da vertical, slice futuro).
- Frontend de Asset (`apps/web`) — plano próprio (AR‑13); este slice entrega as queries de
  `09_COMMAND_MODEL.md` §3.
- OM como Organization independente (G2) — o slice implementa G1.
- IA / pontuação de prioridade oculta (constituição §22–§23).

## Comportamento e regras de negócio

Detalhe completo em `docs/asset/05`…`09`. Resumo do comportamento esperado:

### Cenário A — corretiva com estoque local (fluxo feliz)

1. Registra‑se a falha; abre‑se `WorkOrder` para o veículo → resolve **1** `ContractVersion` + `CoverageLine`
   ativa no instante e **congela** o `ContractContext` (I‑SLI‑1/2).
2. Identifica‑se a peça necessária; resolve‑se `Applicability` da peça ao veículo na configuração vigente —
   retorna a asserção **com `evidence_ref`**, nunca só `true` (I‑APP‑1).
3. Resolve‑se `Entitlement` da peça via `Evaluation → Decision` governada do Core (I‑SLI‑4); resultado
   `GRANTED`.
4. Calcula‑se `available(peça, oficina, SERVICE_SLI)` com `AvailabilityBreakdown` (I‑INV‑1); há estoque.
5. Reserva‑se o material (`ReserveMaterialForWorkOrder`) — transação única `sustainment`+`asset` (B1);
   `Σ reservado ≤ demandado` (I‑WO‑2).
6. WO → `READY` → `SCHEDULED` → `IN_PROGRESS` (veículo → `IN_MAINTENANCE`); executa tarefas; consome material
   (`ConsumeStock`); registra disposição do componente removido.
7. `TECHNICALLY_COMPLETE` → `VALIDATION` → `COMPLETED`; `PostMaintenanceValidation` passou; veículo →
   `AVAILABLE` (`returned_to_service`, I‑WO‑1, I‑VEH‑3).
8. Histórico e projeções (dashboard, fleet view, `FailureRecord`) atualizados.

### Cenário B — corretiva sem estoque local

Passos 1–4 iguais; em 4, `available` na oficina = 0. Então: sistema encontra estoque autorizado em outra
`StockLocation`; `RequestStockTransfer` → `DispatchStockTransfer`; WO entra em `WAITING_MATERIAL` (T3,
I‑WO‑4); estoque `IN_TRANSIT`; `ReceiveStockTransfer` (pode ser parcial, `Σ recebido ≤ despachado` —
I‑INV‑4); material reservado à WO; WO sai de `WAITING_MATERIAL` (T4); segue como A a partir do passo 6.

### Regras exercidas por teste, sem fluxo completo

- **C (disputa)**: `PRODUCTION` × `SERVICE_SLI` × `COMMERCIAL` pela mesma peça física com `on_hand`
  insuficiente → a alocação produz um `Decision` explicável; a demanda que perde recebe recusa com
  `decision_ref` (I‑INV‑2, I‑SLI‑5). Estoque protegido por contrato não é tomado por outro propósito sem
  `Decision`.
- **D (supersessão)**: superseder revisão de peça 2→3 **não** altera baselines as‑maintained históricas
  (I‑PRT‑1); planejamento novo passa a propor a rev. 3 **se aplicável** (I‑APP‑2).
- **E (contrato expira com WO aberta)**: emendar o contrato depois da abertura da WO → o dossiê da WO cita a
  versão vigente à época em todos os eventos anteriores à emenda (I‑SLI‑1/3).

### Máquina de estados da `WorkOrder`

Estados e transições T1–T17 na ADR do slice §2. Toda transição emite exatamente um evento + auditoria
(I‑WO‑3); `CANCELLED`/`INTERRUPTED`/`WAITING_AUTHORIZATION` exigem `reason`.

### Prioridade

`PriorityScore` (0..100) é função pura de fatores + pesos de uma `Rule` versionada; a resposta do dashboard
carrega o **breakdown** e `evaluation_ref` (I‑WO‑5). Sem IA (constituição §22).

## Critérios de aceite

O teste ponta a ponta de A7 (cenários A e B) responde, **com evidência para cada resposta** (constituição §47):

1. Qual veículo? · 2. Qual configuração (na data)? · 3. Qual OM/site? · 4. Qual contrato? · 5. Qual versão do
contrato (na data)? · 6. Que ação de manutenção? · 7. Qual peça? · 8. A peça é aplicável? (asserção +
evidência) · 9. Onde a peça existe? · 10. Quanto está realmente disponível? (breakdown) · 11. Pode ser
reservada? · 12. O que bloqueia a execução? · 13. Qual o SLA? · 14. O que a oficina faz a seguir? · 15. Por
que essa tarefa é prioritária? (breakdown) · 16. Que evidência sustenta cada resposta?

Além disso:

- Invariantes I‑VEH/CFG/PRT/APP/INV/SLI/WO/SEC de `07_INVARIANTS.md` cobertos por teste (positivo e negativo).
- Cada transição T1–T17 com teste; transição não listada → recusa com motivo.
- Cenários C, D, E exercidos por teste de invariante.
- `grep` não encontra: lógica de cobertura fora de `Rule`/`Evaluation`; string `livestock` em
  `packages/asset_*`, `packages/sustainment_*`, `apps/api/asset/`.
- `tests/architecture` verde varrendo `asset` (Core não importa `asset`; `asset` não importa `livestock`).
- Contrato OpenAPI **aditivo**: subconjunto de Livestock inalterado (`SHARED_CHANGE_PROTOCOL.md` §7); rotas
  novas com 401/403 declarados.
- Gate completo verde: `TITAN_REQUIRE_INTEGRATION_DB=1 pytest`, `ruff check .`, `ruff format --check .`,
  `mypy`, `alembic check` (com o `env.py` de Asset → "no changes").
- `pg_dump --schema-only` do schema de Livestock idêntico antes/depois de A3.
- Revisão adversarial (Claude) sem BLOQUEADOR; revisão de integração (Gemini) sem defeito crítico de
  workflow (constituição §37, §49).

## Plano técnico

### Capacidades e arquivos afetados

| Camada | Arquivos (a criar, incrementalmente por passo A2–A7) |
|---|---|
| Domínio | `packages/asset_domain/**`, `packages/sustainment_domain/**` (entidades/VOs/eventos de `05`/`08`) |
| Aplicação | `packages/asset_application/**` (comandos/queries de `09`; `authorization.py`; `AssetOperationContext`), `packages/sustainment_application/**` (`WorkOrder` workflow; `Entitlement` via Core; `WorkshopDashboard` projeção) |
| Infra | `packages/asset_infrastructure/persistence/**` (repos, `metadata.py`, `migrations/` — A‑M1), `packages/sustainment_infrastructure/persistence/**` |
| HTTP | `apps/api/asset/**` (routers + `dependencies.py`), registrado em `apps/api/_registry.py` (P3 — Shared Integration) |
| Validação | `apps/validacao/asset/**` (roteiros A e B) |
| Ledger | `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — entrada por passo, no mesmo commit |

Nenhum arquivo `packages/core_*` / `packages/livestock_*` / `apps/api/livestock_*` é tocado por qualquer
passo A*. `apps/api/_registry.py` e `apps/worker/dispatch.py` são pré‑requisitos de Shared Integration (P3/P4).

### Contratos, persistência, concorrência, idempotência, erros

- **Contratos**: comandos de intenção de negócio (`09` §"Semântica transversal"); rotas espelham comandos
  (`POST /asset/work-orders/{id}/reserve-material`), não `PATCH` de campo.
- **Persistência**: schema `core_audit`; FK compostas por Organization (ADR‑0077); RLS por
  `titan.organization_id` sob role restrita; carimbo `titan.module_owner=asset` / `=sustainment`.
- **Concorrência**: `version:int` por agregado → `OptimisticConcurrencyConflict` (409); `SELECT … FOR UPDATE`
  das `StockPosition` afetadas antes de calcular/gravar reservas/ajustes/transferências (padrão
  `livestock_infrastructure/persistence/transformation_locking.py`).
- **Idempotência**: `core_application.idempotency` em todo comando com efeito externo.
- **Erros**: `application/problem+json` no padrão de `apps/api/main.py`; `401` vs `403` distintos; recurso
  fora do `site_scope` → `404` sem vazar existência.

### Impacto em arquitetura, segurança e tenancy

Ver ADR do slice §"Impacto de Segurança". Resumo: RLS por Organization inalterado; `site_scope` (G1)
aplicado antes da resolução; autorização por permissão; nenhum conceito de Asset no Core; entitlement e
prioridade são decisões governadas do Core.

### Impacto de dados, migration e rollback

Ver ADR do slice §"Impacto de Migração". Tabelas novas apenas; ambiente Alembic próprio de `asset` (A‑M1),
dependente de P0 (S‑M1–S‑M3); `alembic upgrade heads` do zero; `alembic check` limpo; `pg_dump` de Livestock
inalterado; rollback por *branch label* `asset`.

### Integrações, compatibilidade, performance

- Sem integração externa no slice.
- Compatibilidade: OpenAPI aditivo; processamento de mensagens de Livestock idêntico.
- Performance: views operacionais (dashboard, fleet) como **read models** / projeções alimentadas por evento
  (constituição §45); sem denormalização prematura do domínio.

## Verificação e observabilidade

- **Testes automatizados**: invariantes de domínio/aplicação; concorrência de estoque contra Postgres real;
  autorização/RLS sob role restrita; contrato de API; migração (`pg_dump` diff); integração ponta a ponta A e
  B; negativos de cada transição e de cada invariante ("o que NUNCA pode acontecer" — `07`).
- **Roteiro manual/API**: `apps/validacao/asset/` executável contra API + PostgreSQL + Keycloak reais, nos
  moldes de `apps/validacao/` de Livestock.
- **Observabilidade**: logs estruturados com `correlation_id`; eventos `asset.*` no `event_log` + cadeia de
  integridade + checkpoint; `module_owner`/`vertical_id` nos eventos para responder "mudança de Asset afetou
  Livestock?" sem acoplar domínios (`MULTI_VERTICAL_CI_GATES.md`, constituição §44).

## Documentação afetada

- ADR do slice (`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md`) → alocar número na integração.
- `docs/architecture/verticals.toml` → adicionar `sustainment` como sub‑namespace de evento de `asset` e, se
  A3 decidir, `migration_location` de `sustainment` (**PR de Shared Integration** separado).
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` → entrada por passo A2–A7 no mesmo commit.
- `docs/asset/` → documentos diferidos (10, 12–18) produzidos conforme `20` §4.
- `MULTI_AGENT_ARCHITECTURE_REVIEW.md` (§49) → produzir após revisões de Claude e Gemini.
- Esta SPEC → `docs/asset/specs/approved/` no ACCEPT; `docs/asset/specs/implemented/` ao fim de A7 (mesmo
  lifecycle de `docs/specs/README.md`, namespaced por vertical).

## Riscos, alternativas e perguntas abertas

Riscos completos em `docs/asset/19_RISK_REGISTER.md` (B1, H1–H3, AR‑01..15, PR‑01..04).
Principais para esta SPEC:

| Risco | Trade‑off | Recomendação |
|---|---|---|
| AR‑01 disponibilidade como número | simplicidade vs explicabilidade | `available` sempre calculado + breakdown; disputa → `Decision` |
| AR‑02 contexto contratual não congelado | menos código vs correção temporal | `ContractContext` VO imutável resolvido por tempo antes de qualquer regra |
| AR‑03 entitlement como `if` | rapidez vs auditabilidade/governança | delegar ao Core; `grep` no gate de A4 |
| AR‑05 perda de inventário concorrente | performance vs correção | `version` + `FOR UPDATE`; teste de concorrência real |
| AR‑07 máquina de estados | copiar Maximo vs derivar | derivada (ADR §2); toda transição = evento |

**Decisões humanas ainda necessárias (bloqueiam A2 / código):**

- **A** — aceitar a estratégia de migrations D→C (`docs/architecture/DECISIONS_REQUIRED_PHASE0.md`).
- **B** — confirmar B1 (uma vertical, dois pacotes) — fixada nesta ADR, precisa do ACCEPT.
- **F** — cadeia de integridade F1 + exigir o teste de concorrência (P2) antes de A2.
- **G** — confirmar G1 para o slice.
- **P0** — mergear a stack `integration/core/parallel-vertical-foundation`.
- **P3** — `apps/api/_registry.py` aditivo (pré‑req de A5).

Perguntas abertas menores (resolver em A1/A3): `sustainment` compartilha o ambiente de migrations de `asset`?
`Applicability` é agregado próprio ou entidade de `PartRevision`? `StockPosition` já com `lot`/`serial`
opcionais? (candidatos em `06` §6).
