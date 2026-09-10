# CURRENT_PACKAGE_CLASSIFICATION — Classificação dos módulos atuais

**Versão:** 1.0
**Status:** Proposta para revisão (Fase 2 — nenhum código movido)
**Data:** 10 de setembro de 2026

Classificação de cada package/módulo relevante como: **CORE**, **LIVESTOCK**,
**SHARED_KERNEL**, **INFRASTRUCTURE**, **UNCERTAIN** ou **MISPLACED**.

> Regra: *não mover código ainda*. A coluna "Ação recomendada" descreve o destino,
> não uma autorização.

---

## 1. Pacotes de `packages/`

| Package | Responsabilidade atual | Dependências (saída) | Classificação | Problema detectado | Ação recomendada |
|---|---|---|---|---|---|
| `shared_kernel` | Identificadores opacos tipados, `UniversalReference`, primitivas temporais (`Clock`, valid-time/known-time), serialização canônica `titan-json-v1` | nenhuma (base do grafo) | **SHARED_KERNEL** | Nenhum. 321 LOC, coeso. | Manter. Congelar como está; toda adição exige justificativa de universalidade. Não virar "common". |
| `core_domain` | Invariantes universais: identidade, autorização, policy, rule, evaluation, decision, decision_governance, evidence, facts, provenance, verification, dossier, corrections, normative, relations, projections, synchronization, events, crypto | `shared_kernel` | **CORE** | Nenhum vazamento de vertical. `__init__.py` é a superfície pública de fato, sem `__all__` nem teste de estabilidade. | Manter. Adicionar `__all__` + teste de superfície pública (Passo 5 do plano). |
| `core_application` | Casos de uso e portas: outbox, inbox, idempotency, concurrency, timestamping, integrity_checkpoint, event_log, document_service, serviços policy/rule/evaluation/decision/dossier/evidence/fact/relation/correction/synchronization/provenance | `core_domain`, `shared_kernel` | **CORE** | `operational_support.py` é projeção diagnóstica do fluxo assíncrono (outbox/claims) — genuinamente horizontal, mas confirmar que não assume forma de payload de vertical. | Manter. Auditar `operational_support.py` quanto a acoplamento a payloads específicos. |
| `core_infrastructure` (exceto `persistence/migrations`) | Adapters PostgreSQL/PostGIS, RabbitMQ (+consumer), storage, rate_limiter, crypto, log_redaction, pdf, authentication, organization_context | `core_application`, `core_domain`, `shared_kernel`, libs externas | **INFRASTRUCTURE** (do Core) | `persistence/*` é importado diretamente por `livestock_*` (~33x). Dependência de infraestrutura interna, não de contrato. | Manter. Onde a vertical precisa (porta de eventos, `MetaData`), formalizar como contrato explícito re-exportado. |
| `core_infrastructure/persistence/migrations` | **Único** ambiente Alembic + história linear para Core **e** Livestock; `env.py` importa tabelas de `livestock_infrastructure` | `core_infrastructure.persistence`, **`livestock_infrastructure.persistence`** | **MISPLACED** (parcialmente) | O ambiente de migrations do Core conhece a vertical. Exceção nomeada no teste de fronteira. Impede versionar/reverter uma vertical isoladamente e obriga o `env.py` a crescer por vertical. | Cada vertical possui o próprio ambiente Alembic; `MetaData` continua compartilhada só para FK. Fazer para Livestock primeiro, com diff de schema. |
| `core_integrity` | Cadeia de hash de eventos, checkpoints de integridade | `shared_kernel` (e tipos do Core) | **CORE** | Nenhum. 628 LOC. | Manter. |
| `livestock_domain` | Animal, propriedade, movimento, lote, medicação, prescrição, tratamento, reprodução, qualificação, transformação, captura territorial, embargo ambiental, contraparte externa | `core_domain`, `shared_kernel` | **LIVESTOCK** | Nenhum. Fronteira correta. | Manter isolada. |
| `livestock_application` | 66 serviços: elegibilidade por mercado, cobertura sanitária, dossiê, ERP inbox/outbox, market supply/optionality, temporalidade, territorial, verificação | `core_domain`, `core_application`, `core_infrastructure.persistence` (events/orgs), `shared_kernel` | **LIVESTOCK** | Contém `*_workflow.py` ad hoc (workflow de domínio da vertical — correto). `authorization.py` e `event_recorder.py` são padrões que Asset vai espelhar. | Manter isolada. Usar `authorization.py` / `event_recorder.py` como referência de padrão para `asset_application`. |
| `livestock_infrastructure` | Repositórios transacionais, `geodata/car_client`, `persistence/metadata.py` (alias da `MetaData` do Core), simulador SISBOV HTTP, provider de explicação IA | `core_infrastructure.persistence`, `core_domain`, `shared_kernel` | **LIVESTOCK** | `persistence/metadata.py` reusa `organization_metadata` do Core (necessário para FK). Tabelas no schema `core_audit`. | Manter isolada. Asset replica o padrão `metadata.py`. |

---

## 2. Executáveis de `apps/` (não são módulos de negócio; classificados quanto a acoplamento a vertical)

| App / módulo | Responsabilidade | Classificação | Problema detectado | Ação recomendada |
|---|---|---|---|---|
| `apps/api/main.py` | Composição FastAPI: middlewares, handlers de erro, inclusão de routers | **INFRASTRUCTURE** (composição) | Importa cada router de Livestock por nome; sem registry; ponto de conflito por vertical | Registry de routers iterável; `main.py` deixa de nomear verticais |
| `apps/api/authentication.py`, `configuration.py`, `problem.py`, `pagination.py`, `verification.py`, `policy_governance.py` | Adapters HTTP do Core | **CORE** (adapter HTTP) | Convivem no mesmo diretório plano das verticais | Mover para `apps/api/core/` (ou manter, mas convencionar) |
| `apps/api/livestock_*.py` (14 módulos) | Routers + composição HTTP da vertical Livestock | **LIVESTOCK** (adapter HTTP) | Diretório plano; sem subpacote | Mover para `apps/api/livestock/`; Asset nasce em `apps/api/asset/` |
| `apps/api/livestock_dependencies.py` | Raiz de composição HTTP da vertical (HTTP→OIDC→OrganizationContext→Permission→Service→transação→RLS→repo) | **LIVESTOCK** (composição) | — | **Referência de padrão** para `apps/api/asset/dependencies.py` |
| `apps/api/geodata_dependencies.py` | DI de geodata (CAR) | **LIVESTOCK** | Nome não prefixado | Mover para `apps/api/livestock/` |
| `apps/worker/main.py` | Loop do worker, reconciliação de outbox, consumo de inbox | **INFRASTRUCTURE** (composição) | OK em si; depende do registry abaixo | Manter; consumir registry real |
| `apps/worker/livestock_handlers.py` | `WorkerHandlerRegistry` cujo `resolve()` ignora o envelope e devolve sempre o handler de Livestock | **MISPLACED** | Não é despacho; assume vertical única | Despacho real keyed por `message_type`/vertical; handler de Livestock inalterado |
| `apps/bootstrap`, `apps/bootstrap_admin`, `apps/seed`, `apps/demo`, `apps/keycloak_profile_setup`, `apps/provision_runtime_database_role.py`, `apps/grant_local_admin_governance.py` | Provisionamento e bootstrap de ambiente | **INFRASTRUCTURE** | `apps/seed_test_livestock_data.py` é específico de Livestock (nome já indica) | Manter; adicionar seed de Asset quando houver slice |
| `apps/validacao/` | Roteiros manuais executáveis | **INFRASTRUCTURE** (verificação) | Mistura roteiros Core e Livestock | Convencionar subpasta por vertical quando Asset existir |
| `apps/web/` | Frontend React único | **LIVESTOCK** (na prática) | `entityKinds.ts` e páginas acopladas a conceitos de Livestock | Fora de escopo do backend; plano de UI próprio para Asset |

---

## 3. Contagem de testes (raio de impacto de qualquer reorganização)

| Suite | Arquivos `test_*.py` |
|---|---:|
| `tests/core_domain` | 28 |
| `tests/core_integrity` | 2 |
| `tests/application` | 31 |
| `tests/api` | 8 |
| `tests/infrastructure` | 28 |
| `tests/integration` | 85 |
| `tests/architecture` | 1 |
| `tests/livestock_domain` | 19 |
| `tests/livestock_application` | 69 |
| `tests/livestock_infrastructure` | 2 |
| `tests/shared_kernel` | 3 |
| `tests/unit` | 5 |

`tests/integration` (85) é o maior vetor de regressão para qualquer mudança em
migrations ou composição. Toda etapa de reorganização precisa manter esta suite
verde sem alteração de asserção (ver `MIGRATION_SAFETY` em
`CORE_EXTRACTION_RISKS.md`).

---

## 4. Síntese da classificação

- **SHARED_KERNEL:** `shared_kernel` (1 package, mínimo, saudável).
- **CORE:** `core_domain`, `core_application`, `core_integrity`, adapters
  `core_*` de `apps/api`. Limpos de vertical.
- **INFRASTRUCTURE (Core):** `core_infrastructure` (adapters), composição de
  `apps/`.
- **LIVESTOCK:** `livestock_domain`, `livestock_application`,
  `livestock_infrastructure`, `apps/api/livestock_*`, `apps/web`. Isolada.
- **MISPLACED:** `core_infrastructure/persistence/migrations` (ambiente único
  conhece a vertical); `apps/worker/livestock_handlers.py` (não faz despacho).
- **UNCERTAIN:** nenhum módulo genuinamente ambíguo. `operational_support.py`
  merece uma verificação pontual, mas a hipótese é CORE.

**Não há nenhum package que precise ser dividido entre Core e vertical.** Os
únicos ajustes são de *ambiente de migrations* e *composição*, não de domínio.
