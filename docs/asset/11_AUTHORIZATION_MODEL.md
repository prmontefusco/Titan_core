# 11 — AUTHORIZATION MODEL — Titan Asset & Sustainment (primeiro slice)

**Status:** Discovery. **Data:** 10/09/2026. **Lane:** Asset.
Resolve a **decisão G** de `docs/architecture/DECISIONS_REQUIRED_PHASE0.md` (escopo OM/Site — HIGH **H2** de
`PHASE0_ADVERSARIAL_REVIEW.md`) modelando os cenários reais de acesso **antes** de tocar o Core
(constituição §18, §26, §38).

Princípios (constituição §26): menor privilégio · isolamento de tenant · escopo de organização ·
autorização **por permissão, nunca por papel** · acesso cross‑organization explícito · operação privilegiada
auditável · **autorização antes da resolução/divulgação do dado** · fail closed.

---

## 1. Cenários reais de acesso (a fonte da decisão)

| Ator | Escopo natural | O que faz | Vê |
|---|---|---|---|
| Técnico de oficina | **uma oficina / um site** | executa tarefas de WO | WOs da sua oficina; veículos no site; estoque local |
| Planejador de oficina | **um ou mais sites** | abre/prioriza WO | frota e dashboard dos sites; contexto contratual dos veículos |
| Logístico | **um conjunto de `StockLocation`** (pode cruzar sites) | transfere, reserva, ajusta | disponibilidade na sua sub‑rede; transferências |
| Gestor de contrato SLI | **um ou mais `SLIContract`** (cobre vários sites) | acompanha SLA/cobertura | frota coberta, OMs, WOs e SLA de tudo sob aqueles contratos |
| Engenharia | **Organization inteira (leitura)** | aplicabilidade, supersessão, falhas recorrentes | catálogo, configurações, `FailureRecord` de toda a frota (confiabilidade precisa do todo — constituição §19) |
| Representante da OM / cliente | **só a própria OM/site** (leitura) | acompanha reparos | veículos, WOs e status de contrato **da sua OM apenas** |

**Conclusão:** dentro da Organization operadora existem atores **amplos** (engenharia, gestor sênior) e
atores **restritos a site(s)**. Um `SELECT` por Organization **não** é suficiente para os restritos —
confirma o risco H2.

## 2. Decisão G — recomendação

### G1 (recomendada) — escopo de site na vertical; RLS por Organization no Core; nada de OM no Core

| Camada | Mecanismo |
|---|---|
| **Tenant (hard)** | RLS por `titan.organization_id` sob role `NOLOGIN NOSUPERUSER NOBYPASSRLS`; FKs compostas por Organization (ADR‑0002/0003/0077). Inalterado. |
| **Contexto da vertical** | `AssetOperationContext` (espelha `LivestockOperationContext` — `ASSET_VERTICAL_BOOTSTRAP_PLAN.md` §3) envolve o `OrganizationContext` do Core e adiciona `site_scope: SiteScope` — `ALL` ou `frozenset[CustomerSiteId]`, e `location_scope`/`contract_scope` análogos quando relevantes. |
| **Derivação do escopo** | uma `Policy`/`Rule` **governada** do Core resolve, a partir das memberships/grants do principal, **quais sites/localizações/contratos** ele pode ver → produz um `Decision` auditável ("site A: concedido via grant G; site B: negado"). O `site_scope` é o resultado dessa decisão, não um campo solto. |
| **Frequência da derivação (achado da revisão de integração — `MULTI_AGENT_ARCHITECTURE_REVIEW.md`)** | a `Decision` de escopo **não** é recalculada a cada comando/query — seria reexecutar o pipeline de `Evaluation`/`Decision`/auditoria do Core em toda leitura, incorreto tanto em performance quanto em semântica (`Decision` representa decisão de negócio, não cache de ACL). O `site_scope` é resolvido **uma vez por sessão/token de autenticação** (ao montar o `AssetOperationContext`, junto com o `OrganizationContext`) e fica embutido no contexto pelo resto da requisição/sessão; recalcula‑se só quando a sessão é renovada ou um evento de mudança de membership/grant invalida o cache. O `Decision` correspondente é o registro auditável de **quando** o escopo foi concedido, não de cada uso dele. |
| **Aplicação do escopo** | todo comando/query da vertical valida permissão **e** `site_scope` (já resolvido no contexto) **antes** de resolver dado de negócio (I‑SEC‑2). Repositórios recebem o contexto e acrescentam o predicado (`WHERE site_id IN (...)`, `WHERE location_id IN (...)`); `ALL` = sem predicado adicional. |
| **Defesa em profundidade** | além do predicado de aplicação, RLS por Organization continua sendo a barreira que nenhum bug de query fura entre tenants. |

**Nenhum conceito `OM`/`MilitaryOrganization`/`CustomerSite`/`Workshop`/`Vehicle` entra em `packages/core_*`
ou `shared_kernel`** (constituição §18). `CustomerSite` é entidade de `asset_domain` (`05` §1.11).

### G2 (alternativa por deployment, decidida em A1) — OM = Organization

Se, para um cliente específico, cada OM é uma entidade independente com usuários próprios, modela‑se cada OM
como uma `Organization` do Core, e a cobertura do contrato da operadora sobre veículos da OM usa
**compartilhamento cross‑Organization** (primitivas que o Core já tem: `core_domain.policy_sharing`,
`shared_decision`, `shared_policy_access_log` — `CORE_REUSE_ASSESSMENT.md`). Impacto: identidade/memberships
por OM passam a existir (uma Organization por OM). A cadeia de integridade **não** é afetada por essa escolha
— ela já é por agregado, não por Organization (decisão F resolvida), então G2 não introduz nem resolve nada
em relação a H1. Não é o padrão; é uma opção que A1 escolhe conforme a estrutura real do cliente.

### G3 (rejeitada agora) — primitiva genérica de sub‑escopo no Core

Especulativa (constituição §38). Só via `CORE_CHANGE_REQUEST` (`CORE_CHANGE_REQUEST_TEMPLATE.md`) **depois**
que G1 provar a necessidade **e** que Livestock tenha o caso análogo ("propriedades sob um mesmo grupo"),
demonstrando horizontalidade. O template já tem o exemplo redigido.

---

## 3. Catálogo de permissões (por permissão, nunca por papel)

Formato `ASSET_<AGREGADO>.<AÇÃO>` / `SUSTAINMENT_<AGREGADO>.<AÇÃO>` — as usadas em `09_COMMAND_MODEL.md`.
Novas permissões entram no catálogo do Core (`core_identity.permissions`, RLS explícita — migration
`20260909_0085`) via migration da vertical.

| Domínio | Permissões |
|---|---|
| Vehicle | `ASSET_VEHICLE.{REGISTER,SET_BASELINE,RECORD_METER,CORRECT_METER,TRANSITION,READ}` |
| Configuration | `ASSET_CONFIG.{PUBLISH,SUPERSEDE,READ}` |
| Part | `ASSET_PART.{REGISTER,ADD_REVISION,SUPERSEDE,EDIT_INTERCHANGE,READ}` |
| Applicability | `ASSET_APPLICABILITY.{ASSERT,WITHDRAW,READ}` |
| Inventory | `ASSET_INVENTORY.{OPEN_POSITION,ADJUST,RESERVE,RELEASE,ALLOCATE,CONSUME,TRANSFER_REQUEST,TRANSFER_DISPATCH,TRANSFER_RECEIVE,READ}` |
| Site | `ASSET_SITE.{REGISTER,READ}` |
| Contract | `SUSTAINMENT_CONTRACT.{REGISTER,ISSUE_VERSION,AMEND,READ}` |
| Entitlement | `SUSTAINMENT_ENTITLEMENT.{RESOLVE,AUTHORIZE_EXCEPTION}` |
| Work Order | `SUSTAINMENT_WO.{OPEN,ADD_TASK,DEMAND_MATERIAL,RESERVE_MATERIAL,RECALC_PRIORITY,TRANSITION,EXECUTE,RECORD_REMOVAL,TECH_COMPLETE,VALIDATE,CLOSE,CANCEL,RECORD_FAILURE,READ}` |
| Dashboard | `SUSTAINMENT_DASHBOARD.READ` |

Papéis (ex.: "Técnico de oficina", "Gestor de contrato") são **agrupamentos de permissões** na camada de
identidade — a autorização de código sempre checa a **permissão**, nunca o papel
(`livestock_application.authorization` como referência de padrão).

## 4. Regras de autorização por classe de operação

| Classe | Regra |
|---|---|
| **Leitura de dado de negócio** | permissão `*.READ` **+** `site_scope`/`contract_scope` aplicado no predicado da query, **antes** de montar a resposta (constituição §26). Recurso fora do escopo → `404` sem vazar existência (I‑SEC‑2). |
| **Mutação de agregado** | permissão específica + `expected_version` + idempotência + `site_scope` do agregado alvo dentro do escopo do principal. |
| **Operação privilegiada** (`AdjustStock`, `AmendContract`, `WithdrawPartApplicability`, `CancelWorkOrder`, `TransitionVehicleLifecycle` fora do fluxo normal) | além do acima: `reason` obrigatório + evento de auditoria dedicado + (quando a política exigir) `DecisionGovernance` do Core (proposta/revisão). |
| **Entitlement / prioridade** | decididos por `Rule` governada → `Decision` explicável; o chamador precisa de `SUSTAINMENT_ENTITLEMENT.RESOLVE` mas **não** pode sobrepor o resultado sem uma `Decision` de exceção autorizada (I‑SLI‑5). |
| **Acesso a documento técnico / desenho / 3D** | `Evidence`/`document_service` do Core; o link só é resolvido após a mesma checagem de permissão + escopo; documento de outro tenant nunca é servido (constituição §26). |
| **Cross‑organization** (representante da OM lendo dados sob a operadora, ou operadora vendo OM‑Organization em G2) | **explícito**, via grant/compartilhamento registrado e auditado (`shared_policy_access_log`); nunca um endpoint global por conveniência (constituição §26). |

## 5. Fail closed

- Sem `AssetOperationContext` resolvido → recusa (não "assume ALL").
- `site_scope` não resolúvel (política falha, membership ambígua) → recusa, não escopo vazio silencioso.
- Permissão ausente → `403`; princípio não autenticado → `401` (distinção preservada — padrão de
  `apps/api/main.py`).
- Agregado sem `organization_id`/`site_id` quando o tipo exige → erro de modelo, não default.

## 6. Testes de autorização exigidos (constituição §36)

| Teste | Garante |
|---|---|
| RLS por tabela nova sob role restrita (`test_organization_postgresql.py` como padrão) | I‑SEC‑1 — nenhum vazamento entre Organizations |
| `site_scope` — principal com `{A}` lista frota → só A; acessa WO de B → `404` sem vazar | I‑SEC‑2 (decisão G) |
| escopo aplicado **antes** da resolução — query fora do escopo não executa `SELECT` de negócio | constituição §26 |
| permissão, não papel — remover a permissão (mantendo o papel) bloqueia a ação | constituição §26 |
| operação privilegiada sem `reason` → recusa; com `reason` → evento de auditoria dedicado | constituição §24 |
| entitlement não sobreponível sem `Decision` de exceção autorizada | I‑SLI‑4/5 |
| cross‑org sem grant → recusa; com grant → acesso + entrada em `shared_policy_access_log` | constituição §26 |
| concorrência: dois comandos no mesmo agregado → um `OptimisticConcurrencyConflict` | constituição §36 |

## 7. O que fica para A1 / CCR

- **A1 decide** G1 vs G2 conforme a estrutura real do(s) cliente(s) do primeiro contrato.
- Se, durante a implementação, `site_scope` na vertical se mostrar insuficiente (ex.: precisa valer também
  para capacidades do Core que a vertical consome), abrir **`CORE_CHANGE_REQUEST`** para um `Scope` genérico
  opcional no `OrganizationContext` — provando horizontalidade com o caso de Livestock. Até lá, **nada disso
  é implementado** (constituição §18).
