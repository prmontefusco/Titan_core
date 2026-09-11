# VERTICAL_OWNERSHIP_MATRIX — Propriedade de caminhos, identificador de vertical e fonte da verdade

**Status:** Proposta para revisão. Documentação apenas.
**Data:** 10 de setembro de 2026
**Base:** `PARALLEL_VERTICAL_DEVELOPMENT_PROTOCOL.md`, ADR‑0001, `tests/architecture/test_dependency_boundaries.py`.

Este documento é a **fonte normativa** de "quem é dono de quê". O portão de CT que o aplica está em
[`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §"File Ownership Guard".

---

## 1. Identificador de vertical (`vertical_id`)

Cada vertical tem um `vertical_id` **estável, único, minúsculo, sem espaço**, independente do nome de exibição.

| `vertical_id` | Nome de exibição | Estado |
|---|---|---|
| `livestock` | Titan Livestock | ativo |
| `asset` | Titan Asset & Sustainment | em bootstrap |

Regras:

- O `vertical_id` **nunca muda** depois de registrado (é usado em `titan.module_owner`, namespaces de evento,
  ownership de migration, observabilidade e registro de composição).
- Não pré‑criar identificadores para verticais que não existem. `docs/verticals/titan_zfm_logistics.md` é um
  esboço de produto, **não** um `vertical_id` registrado.
- O `vertical_id` **não vaza** para a semântica de domínio (não é campo de entidade, não entra em regra de
  negócio) salvo necessidade comprovada.
- Se a discovery de Asset decidir que `sustainment` é um segundo pacote da **mesma** vertical, ele compartilha
  o `vertical_id = asset` para efeito de ownership e namespace; se for vertical irmã isolada, recebe
  `vertical_id = sustainment` próprio. Decisão pendente — ver
  [`DECISIONS_REQUIRED_PHASE0.md`](DECISIONS_REQUIRED_PHASE0.md) decisão **B**/§M2 do
  [`PHASE0_ADVERSARIAL_REVIEW.md`](PHASE0_ADVERSARIAL_REVIEW.md).

---

## 2. Fonte da verdade: manifesto de verticais

Para não espalhar a lista de verticais por múltiplos testes e portões, introduzir **um** arquivo declarativo,
consumido por `tests/architecture/` e pelos portões de CI:

```
docs/architecture/verticals.toml        (proposto — criado quando o Passo 1 for executado)
```

Conteúdo conceitual (composição apenas — **sem** comportamento de domínio):

```toml
[livestock]
package_roots      = ["packages/livestock_domain", "packages/livestock_application", "packages/livestock_infrastructure"]
test_roots         = ["tests/livestock_domain", "tests/livestock_application", "tests/livestock_infrastructure"]
api_paths          = ["apps/api/livestock_*.py", "apps/api/geodata_dependencies.py"]   # layout atual
worker_handlers    = ["apps/worker/livestock_handlers.py"]
doc_roots          = ["docs/verticals/titan_zfm_logistics.md"]                          # exemplo; docs de Livestock
event_namespaces   = ["livestock"]
migration_owner    = "titan_livestock"
migration_locations = ["packages/core_infrastructure/persistence/migrations/versions"]  # transitório (ver estratégia de migrations)

[asset]
package_roots      = ["packages/asset_domain", "packages/asset_application", "packages/asset_infrastructure"]
test_roots         = ["tests/asset_domain", "tests/asset_application", "tests/asset_infrastructure"]
api_paths          = ["apps/api/asset/"]
worker_handlers    = ["apps/worker/asset_handlers.py"]
doc_roots          = ["docs/asset/"]
event_namespaces   = ["asset", "sustainment"]     # 'sustainment' aqui sse decisão B = "mesmo vertical_id"
migration_owner    = "titan_asset"
migration_locations = ["packages/asset_infrastructure/persistence/migrations/versions"]
```

O manifesto **não** faz o Core depender de vertical: ele vive na camada de documentação/composição e é lido
por testes e CI, nunca por `packages/core_*`.

Regra de segurança para o teste que consome o manifesto (contra o red flag "auto‑discovery trata pacote
arbitrário como vertical"): a lista de verticais é **explícita neste arquivo**; o teste é genérico sobre a
lista, mas a lista nunca é inferida do sistema de arquivos.

---

## 3. Matriz de propriedade de caminhos

Legenda de lane: **A** = Livestock · **B** = Asset · **C** = Shared Integration.

| Glob | Lane / dono | Observação |
|---|---|---|
| `packages/shared_kernel/**` | C | Contenção rígida (`DEPENDENCY_RULES.md` §4). |
| `packages/core_domain/**`, `packages/core_application/**`, `packages/core_infrastructure/**`, `packages/core_integrity/**` | C | Somente‑leitura para verticais; mudança só via `CORE_CHANGE_REQUEST`. |
| `packages/livestock_*/**` | A | Somente‑leitura para Asset. |
| `tests/livestock_*/**` | A | Asset não altera asserção de Livestock (constituição §21). |
| `apps/api/livestock_*.py`, `apps/api/geodata_dependencies.py`, `apps/api/livestock_dependencies.py` | A | Layout atual; **não** mover enquanto Livestock ativo (restrição §7). |
| `apps/worker/livestock_handlers.py` | A | Idem. |
| `packages/asset_*/**`, `packages/sustainment_*/**` | B | Somente‑leitura para Livestock. Criados incrementalmente. |
| `tests/asset_*/**`, `tests/sustainment_*/**` | B | — |
| `apps/api/asset/**`, `apps/validacao/asset/**`, `apps/worker/asset_handlers.py` | B | Nascem em subpacote próprio. |
| `docs/asset/**` | B | Docs de discovery de Asset. |
| `apps/api/main.py` | C | Ponto de colisão hoje (importa cada router de Livestock por nome + *feature flags*). |
| `apps/api/_registry.py`, `apps/worker/dispatch.py` | C | Ainda não existem; nascem em PR de Shared Integration. |
| `apps/api/authentication.py`, `configuration.py`, `problem.py`, `pagination.py`, `verification.py`, `policy_governance.py` | C | Adapters HTTP do Core. |
| `alembic.ini`, raiz de composição de migrations, registro de `version_locations` | C | Ver [`MIGRATION_CONCURRENCY_STRATEGY.md`](MIGRATION_CONCURRENCY_STRATEGY.md). |
| `packages/*/persistence/migrations/versions/**` | dono = `migration_owner` da vertical | Migration nunca cria/dropa/altera tabela de outro dono (restrição §10). |
| `pyproject.toml`, `uv.lock`, `.python-version` | C | Dependência nova = Shared Integration. |
| `tests/architecture/**`, `tests/integration/**` cross‑vertical | C | — |
| `.github/workflows/**` | C | — |
| `docs/architecture/**`, `docs/adr/**` | C | Docs universais; ADR por processo de alocação de número (§8 do protocolo). |
| `docs/CHECKLIST_DE_IMPLEMENTACAO.md` | C (append por qualquer lane) | Ledger único; cada lane acrescenta sua entrada no mesmo commit da mudança (AGENTS.md). Nunca reescrever entrada alheia. |

Caminhos **não listados** e não cobertos por glob de vertical são, por padrão, **Lane C** (exigem
classificação explícita antes da escrita).

---

## 4. Composição de um PR bem‑formado

| Tipo de PR | Contém | Não contém |
|---|---|---|
| Feature de Asset (Lane B) | caminhos `asset`‑owned + docs de Asset + testes de Asset | qualquer caminho `livestock`‑owned ou Lane C |
| Feature de Livestock (Lane A) | caminhos `livestock`‑owned + docs + testes de Livestock | qualquer caminho `asset`‑owned ou Lane C |
| Shared Integration (Lane C) | apenas caminhos Lane C, com `CHANGE_CLASS=SHARED_INTEGRATION` | mistura com feature de vertical |

Um PR que mistura lanes **falha** no portão de ownership. Um PR de Lane C sem o rótulo `CHANGE_CLASS` **falha**.
Detalhe do mecanismo em [`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md).

---

## 5. `titan.module_owner` como âncora

Toda tabela carimba `titan.module_owner` no comentário/`info` (já é prática em Livestock —
`CORE_REUSE_ASSESSMENT.md` §2). Valores: `titan_core`, `titan_livestock`, `titan_asset`, …
Esse carimbo é a chave usada por: escopo de `alembic check` por vertical, portão de ownership de migration,
detecção de acesso cruzado a persistência e observabilidade. É **enforcement**, não convenção — ver
[`MULTI_VERTICAL_CI_GATES.md`](MULTI_VERTICAL_CI_GATES.md) §"Migration ownership" e §"Database access isolation".
