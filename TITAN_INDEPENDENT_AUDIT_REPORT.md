# Titan Independent Audit Report

**Auditor:** Claude (independent verifier / adversarial reviewer)
**Data:** 2026-08-31
**Commit auditado:** `1e47f7691a85cc9454a6d71120e096173167f17d` (branch `main`)
**Working tree:** 14 arquivos modificados, 59 não rastreados (todo o CUT F / Market Supply está **não commitado**)

---

## 1. Executive Summary

```text
Overall status:                    ORANGE
Architecture compliance:           PARTIAL
Security posture:                  FAIL
Tenant isolation:                  FAIL
Audit/integrity:                   PARTIAL
Market Supply:                     PARTIAL
Test reliability:                  MEDIUM
Codex implementation confidence:   MEDIUM
```

O trabalho de Market Supply é, em estrutura e disciplina de escopo, de alta
qualidade: nenhum endpoint foi criado, nenhuma leitura cross-tenant existe, os
limites de pacote estão limpos, `ruff`/`mypy`/`alembic check` passam e a suíte
completa (1562 testes com PostgreSQL configurado) passa. A tabela
`core_audit.market_supply_query_audit_records` tem RLS real, append-only real e
um teste de integração honesto que prova ambos com role `NOBYPASSRLS`.

Mas três garantias declaradas **não existem de fato**, apenas parecem existir:

1. **Isolamento entre Organizations está quebrado na tabela de grants.**
   `core_audit.authorization_grants` — a tabela que sustenta todo o modelo de
   autorização cross-tenant do Market Supply — **não tem RLS**, e o role de
   runtime `titan_app` (NOBYPASSRLS) tem SELECT/INSERT/UPDATE/DELETE nela.
   Provado empiricamente: uma Organization lê, revoga e apaga o grant de outra.
   Mais cinco tabelas tenant-scoped em `core_audit` têm o mesmo defeito.

2. **Semantic differencing é inerte na composição real.** O código existe, os
   testes unitários passam, mas a chave de correlação do histórico
   (`policy_context_digest`) é o digest da `CandidatePopulationSnapshot`, que é
   único por consulta. Provado: um ataque de subtração de coorte (42 animais →
   41 animais, delta = 1) é **liberado**, e o histórico entregue ao serviço de
   privacidade é sempre de tamanho zero.

3. **Revogação não bloqueia reexecução.** ADR-0070 e ADR-0071 exigem
   explicitamente `query reexecution -> DENIED`. Provado: a mesma idempotency
   key após revogação retorna o agregado previamente liberado, sem reavaliar
   autorização e sem gerar registro de audit.

Nenhuma superfície externa existe hoje, então o risco explorável **agora** está
limitado ao defeito 1 (que é de banco e independe do Market Supply). Os defeitos
2 e 3 tornam-se críticos no instante em que o endpoint F3.5 for criado — e o
Release Gate Package hoje os declara como já satisfeitos.

**Confiança nos relatórios do Codex:** MEDIUM. Os relatórios são detalhados,
honestos sobre o que *não* foi feito, e a disciplina de escopo é real. Porém uma
afirmação central de capacidade ("differencing prova supressão a partir do
histórico auditado") é **contradita** pela verificação independente, e o teste
que a sustenta constrói um estado que o resolver não consegue produzir.

---

## 2. Repository State

| Item | Valor |
| --- | --- |
| Branch | `main` |
| Commit | `1e47f76` — *docs(checklist): registra o ponto de parada de 27 de agosto de 2026* |
| Alterações não commitadas | 14 modificados, 59 não rastreados |
| Migration head | `20260831_0078_create_market_supply_query_audit_records` |
| `alembic current` | `20260831_0078 (head)` — banco local sincronizado |
| `alembic check` | `No new upgrade operations detected` |
| `ruff check .` | `All checks passed!` |
| `mypy` | `Success: no issues found in 677 source files` |
| `pytest` (sem `TITAN_DATABASE_URL`) | **1277 passed, 286 skipped** |
| `pytest` (com `TITAN_DATABASE_URL`) | **1562 passed, 1 skipped** (150s) |

**Observação material:** todo o CUT F (ADRs 0069/0070/0071, specs aprovadas,
9 módulos de aplicação, 1 repositório, 1 migration, 12 arquivos de teste,
~25 documentos de plano) está **não commitado**. Auditei o working tree.

### Ambiente

- `python -m uv run --locked pytest` falha com `uv trampoline failed to
  canonicalize script path`. Usei `.venv\Scripts\python.exe -m pytest`.
- O `.venv` resolve para `C:\programing\Titan\.venv` (visível nos warnings do
  pytest), consistente com a nota do `CLAUDE.md` sobre o repositório
  autoritativo, embora o código auditado esteja em `D:\projects\Titan`.

---

## 3. Codex Claims Verification

| # | Codex claim | Fonte | Evidência independente | Verdict |
| --- | --- | --- | --- | --- |
| 1 | "Teste prova que uma consulta que passaria isoladamente é suprimida por risco de differencing quando existe histórico auditado relacionado" | CHECKLIST, CUT F3.2B | Com o resolver real, o histórico entregue ao privacy service é sempre `0 fingerprints`; subtração de coorte de 1 sujeito é RELEASED | **CONTRADICTED** |
| 2 | "Revogação efetiva bloqueia novas consultas, reexecuções e novos relatórios" | ADR-0071 §8, CHECKLIST F2E | Replay idempotente após revogação devolve o agregado RELEASED anterior, sem audit | **NOT CONFIRMED** |
| 3 | "Se durable audit append falha, nenhum agregado público pode ser retornado" | CUT_F3_5 §4 | Verdadeiro *quando há repositório*. Sem repositório (default do construtor) o agregado é liberado sem audit nenhum | **PARTIALLY CONFIRMED** |
| 4 | "Nenhum aggregate result existe validamente sem snapshot + DisclosureDecision + audit record" | ADR-0071 §4, SPEC F3 | Verdadeiro para `MarketSupplyAggregateResult` (invariante no `__post_init__`). Falso para `public_response`, que é o que o comprador recebe | **PARTIALLY CONFIRMED** |
| 5 | "Append-only por RLS, sem UPDATE/DELETE para runtime" (market supply audit) | Migration 0078, CUT F3.4 | Confirmado com role `NOBYPASSRLS` que recebeu GRANT de UPDATE/DELETE: `rowcount == 0` em ambos | **CONFIRMED** |
| 6 | "RLS protegendo buyer/requester e owner/audit visibility" | Migration 0078 | Policies SELECT/INSERT sobre `record_owner_organization_id`, `FORCE ROW LEVEL SECURITY`; cross-org retorna `()` | **CONFIRMED** |
| 7 | "Nenhum endpoint, rota, query cross-tenant ou visibilidade buyer-facing foi implementado" | CHECKLIST F3.1/F3.2, CUT F3.5 | `grep` em `apps/api/`: zero ocorrências de market supply. Resolver opera só sobre sujeitos fornecidos pelo caller e exclui `ORGANIZATION_MISMATCH` | **CONFIRMED** |
| 8 | "`reference_time` e `knowledge_cutoff` são invariantes obrigatórias" | ADR-0071 §1 | Obrigatórios e validados como UTC em criteria, identity e audit record. Porém **não são amarrados entre si** — audit pode declarar coordenadas diferentes das da população resolvida | **PARTIALLY CONFIRMED** |
| 9 | "Idempotência semântica: mesma chave + digest divergente gera conflito" | ADR-0071 §5 | Confirmado via `IdempotencyService`; `intent_digest` cobre buyer/purpose/policy/version/demand/criteria/reference_time/knowledge_cutoff/key | **CONFIRMED** |
| 10 | "Nenhuma mudança em Dossier, VerificationBundle, Evidence, Evaluation ou Decision" | ADR-0070, execution report | `git status`: nenhum arquivo de `core_integrity` ou dossier/bundle alterado; suíte completa verde | **CONFIRMED** |
| 11 | "Core não absorve conceito vertical" (ADR-0069) | ADR-0069 | `grep market_supply` em `core_domain`/`core_application`/`shared_kernel`/`core_integrity`: zero. Adapter em `livestock_infrastructure` | **CONFIRMED** |
| 12 | "Comportamento público uniforme: denied e privacy-suppressed parecem iguais" | CUT F2D | Confirmado na camada de aplicação: todo não-release mapeia para `{"status": "NOT_RELEASED"}`. Camada HTTP não existe → não verificável | **PARTIALLY CONFIRMED** |

---

## 4. Architecture Compliance Matrix

| Requisito / Invariante | Fonte | Implementação | Testes | Verdict |
| --- | --- | --- | --- | --- |
| Organization é boundary de isolamento; RLS onde é garantia arquitetural | ADR-0070, `AGENTS.md` | RLS ausente em `core_audit.authorization_grants` + 5 tabelas | Nenhum teste de RLS para grants | **FAIL** |
| Ausência de grant nega acesso | ADR-0070 | `MarketSupplyAuthorizationService._assess` → `MISSING_GRANT` | `test_missing_grant_denies_before_privacy_assessment` | PASS |
| Purposes separados (aggregate vs candidate disclosure) | ADR-0070 | `market_supply_authorization.py:12-19`, checagem dupla request+grant | `test_market_supply_authorization.py` | PASS |
| Authorization precede population resolution | SPEC F3 | `assess_aggregate_access` avalia autorização antes de qualquer uso de snapshot | `test_auditable_workflow_persists_authorization_denial_before_population` | PASS |
| Snapshot precede DisclosureDecision | ADR-0071 §4 | `_build_disclosure_decision` recebe `candidate_population_digest` já validado | `test_population_snapshot_digest_must_match_query_fingerprint_context` | PASS |
| DisclosureDecision separada de AuthorizationDecision | ADR-0071 §4B | `DisclosureDecision` (VO imutável) distinto de `MarketSupplyAuthorizationAssessment` | `test_market_supply_privacy.py` | PASS |
| Nenhum result liberável sem snapshot + disclosure + audit durável | ADR-0071 §4, SPEC F3 | Invariante existe em `MarketSupplyAggregateResult`; **ausente** no caminho de `public_response` | Nenhum teste cobre workflow sem repositório | **FAIL** (F-04) |
| Audit durável antes do release | SPEC F3, CUT F3.5 §4 | `_audit_repository.append()` antes de construir result; falha propaga | `test_audit_append_failure_blocks_public_response_mapping` | PASS (quando há repositório) |
| Audit existe para TODOS os resultados | ADR-0071 §2 | Ausente em replay idempotente e no caminho sem repositório | — | **FAIL** (F-02, F-04) |
| Append-only do audit (sem UPDATE/DELETE) | ADR-0071 §2 | RLS sem policy de UPDATE/DELETE + `FORCE RLS` | `test_market_supply_query_audit_is_inserted_append_only_and_rls_isolated` | **PASS** |
| Semantic differencing usa histórico auditado | ADR-0071 §6, SPEC F3 | Código existe; chave de correlação inviabiliza qualquer match | Teste usa estado que o resolver não produz | **FAIL** (F-01) |
| Proteção contra repeated query | ADR-0070, ADR-0071 §1 | Mesma causa raiz de F-01 | Idem | **FAIL** (F-01) |
| Revogação bloqueia novas consultas | ADR-0070, ADR-0071 §8 | `REVOKED_GRANT` no `_assess` | `test_workflow_rechecks_revocation_before_public_release` | PASS |
| Revogação bloqueia **reexecuções** | ADR-0070, ADR-0071 §8 | Replay idempotente não reavalia nada | Nenhum teste | **FAIL** (F-02) |
| Recheck de revogação antes do release (TOCTOU) | SPEC F3 | Recheck **temporal** sobre grant em memória; não há porta de re-leitura | Teste passa grant já revogado | **PARTIAL** (F-03) |
| Idempotência semântica (replay canônico / conflito explícito) | ADR-0071 §5 | `MarketSupplyRequestIdentity.semantic_digest()` → `intent_digest` | `test_idempotent_workflow_replays...`, `..._conflict_blocks_new_audit_append` | PASS |
| `reference_time` / `knowledge_cutoff` obrigatórios | ADR-0071 §1 | `require_utc` em criteria, identity, audit context | Vários | PASS |
| Coordenadas temporais descrevem a população resolvida | ADR-0071 §1/§5 | Não amarradas: audit aceita coordenadas divergentes da snapshot | Nenhum teste | **PARTIAL** (F-06) |
| Resposta pública uniforme (NOT_RELEASED indistinguível) | ADR-0070, ADR-0071 §7 | `MarketSupplyPublicResponseMapper` → `{"status":"NOT_RELEASED"}` sempre | `test_privacy_suppression_keeps_public_response_uniform` | PASS (aplicação) / **UNKNOWN** (HTTP/timing/cache) |
| Nenhum ID individual no payload buyer-facing | SPEC F3 | `aggregate_payload: Mapping[str, Any]` sem schema nem allow-list | Nenhum teste | **PARTIAL** (F-07) |
| Cohort minimums refletem a população real | ADR-0070, ADR-0071 §1 | `organization_count`/`property_count` são asserções do caller | Nenhum teste negativo | **PARTIAL** (F-05) |
| Resolver não faz lookup global de Animal | ADR-0071 §3 | Resolver puramente in-memory sobre sujeitos do caller; exclui `ORGANIZATION_MISMATCH` | `test_market_supply_population.py` | PASS |
| Snapshot preserva universo lógico (authorized_sources/selection/population digests, counts) | ADR-0071 §3 | `internal_universe_summary()` — mas `organization_count` é hard-coded `1`, `property_count` é `None` | Nenhum teste multi-org | **PARTIAL** |
| Nenhum Aggregate Root para CommercialDemand | ADR-0069, ADR-0071 §9 | `CommercialDemandContext` frozen, transitório, sem persistência | `test_market_supply_request.py` | PASS |
| Core não absorve conceito vertical | ADR-0069, `DOMAIN.md` | Zero referências em core packages | — | PASS |
| Sem `domain -> infrastructure` | `ARCHITECTURE.md` | Zero imports invertidos | `mypy` + grep | PASS |
| Sem ML/IA em CUT F | ADR-0069 | Nenhuma dependência de ML | — | PASS |
| Nenhuma linguagem de certificação/aprovação regulatória | ADR-0069, §27 | Módulos são explícitos ("not a guarantee of availability"); docstrings negam Evaluation/Decision | — | PASS |
| Nenhum endpoint antes do HUMAN RELEASE GATE | ADR-0071, SPEC F3 | Nenhuma rota de market supply em `apps/api/` | — | PASS |

---

## 5. Critical Findings

### F-01 — Semantic differencing e repeated-query são estruturalmente inertes no workflow composto

```text
Finding ID:   F-01
Severity:     CRITICAL
Confidence:   HIGH (verificado empiricamente, hipótese testada e não refutada)
```

**Requisito violado**
ADR-0071 §6 ("historico suficiente para semantic differencing e obrigatorio";
"Repeated-query window isolada nao basta quando consultas diferentes podem ser
combinadas para revelar a contribuicao de uma propriedade, Organization ou grupo
raro"); ADR-0070 ("Protecao contra consultas repetidas e differencing e
requisito antes da primeira API agregada cross-Organization de producao");
SPEC F3, critério de aceite "Differencing usa historico auditado de queries
relacionadas".

**Evidência**

O acoplamento entre três pontos torna o controle inalcançável:

1. `packages/livestock_application/market_supply_workflow.py:379-380` — o workflow
   **exige** que o fingerprint aponte para a snapshot:
   ```python
   if snapshot.snapshot_digest != query_fingerprint.policy_context_digest:
       raise ValueError("query_fingerprint policy_context_digest deve referenciar o snapshot.")
   ```
2. `packages/livestock_application/market_supply_population.py:256-274` — o
   `snapshot_digest` é função de `criteria_digest` (que inclui filtros,
   `required_tags`, `excluded_subject_ids`, janela comercial, coordenadas
   temporais), de `resolved_at` e da lista de sujeitos incluídos.
3. `packages/livestock_application/market_supply_privacy.py:255-267` —
   `_same_context()` só considera duas queries relacionadas se o
   `policy_context_digest` for **idêntico**; e
   `market_supply_workflow.py:226-241` busca o histórico filtrando por esse
   mesmo digest.

Consequência lógica: duas consultas com filtros diferentes produzem snapshots
diferentes → digests diferentes → `_same_context()` sempre `False` e
`find_related_query_fingerprints()` sempre vazio. Como `resolved_at` também
entra no digest, **até consultas idênticas** repetidas em instantes diferentes
deixam de ser relacionadas — o `repeated_query_window` também morre.

**Como verifiquei**

Teste independente com o `CandidatePopulationResolver` real
(`scratchpad/audit/test_audit_market_supply_invariants.py::test_A...`,
`::test_B...`) e sonda com repositório instrumentado
(`scratchpad/audit/probe_history.py`):

```text
QUERY A (full cohort, 42 subjects)
  -> differencing history handed to privacy service: 0 fingerprint(s)
  stored records: 1
QUERY B (cohort minus 1, 41 subjects)
  -> differencing history handed to privacy service: 0 fingerprint(s)
  outcome: RELEASED

snap_a.policy_context_digest = bfd278bb46c1a894 ...
snap_b.policy_context_digest = c4be7b55d0d640e0 ...
digests match -> False
```

```text
[AUDIT-B] identical criteria, snapshot digests equal: False
[AUDIT-B] repeat outcome: RELEASED
```

**Por que o teste existente não pega isto**

`tests/livestock_application/test_market_supply_workflow.py:878`
(`test_workflow_uses_audit_history_for_differencing_before_release`) constrói à
mão dois fingerprints com `policy_context_digest=snapshot.snapshot_digest`
**idêntico** e `filter_fingerprint` **diferente**. Esse estado é fisicamente
inatingível: dois conjuntos de filtros distintos não podem produzir a mesma
snapshot. O teste reproduz a implementação de `_has_differencing_risk`, não o
contrato da ADR.

**Impacto**

O ataque canônico que a ADR-0071 §6 nomeia — subtrair uma propriedade/coorte
entre duas consultas — passa sem supressão. Com 42 e 41 sujeitos, o comprador
deduz exatamente a contribuição do sujeito removido. Como o resultado é liberado
com `DisclosureDecision.ALLOW`, o audit registra `RELEASED`: não há sequer
sinal forense de que houve inferência.

**Reprodução**

```bash
PYTHONPATH=. .venv/Scripts/python.exe scratchpad/audit/probe_history.py
```

**Comportamento esperado**
Query B suprimida com `DIFFERENCING_RISK` (delta de 1 < `minimum_subjects=20`).

**Comportamento real**
Query B `RELEASED`, histórico consultado de tamanho 0.

**Correção recomendada**
Separar a chave de correlação semântica do digest da snapshot. O histórico
precisa ser recuperável por um eixo estável — buyer Organization + purpose +
policy_id/version + coordenadas temporais (e/ou geografia normalizada) — com o
`filter_fingerprint` e o `result_subject_count` como material variável a
comparar. O `snapshot_digest` deve continuar existindo como *linkage* de
integridade (ADR-0071 §4), mas não pode ser o eixo de agrupamento do
differencing. Adicionar o teste de subtração de coorte usando o resolver real.

---

### F-02 — `core_audit.authorization_grants` (e mais 5 tabelas tenant-scoped) sem RLS: leitura, revogação e exclusão cross-tenant

```text
Finding ID:   F-02
Severity:     CRITICAL
Confidence:   HIGH (provado no PostgreSQL local com o role de runtime real)
```

**Requisito violado**
ADR-0070 ("Organization permanece o boundary padrao de tenant/isolation");
`AGENTS.md`/`ARCHITECTURE.md` (RLS como garantia arquitetural);
ADR-0071 §3 (o resolver produtivo depende de grants/opt-in íntegros).

**Evidência**

`packages/core_infrastructure/persistence/migrations/versions/5e402311b352_create_authorization_grants_table_for_.py`
cria a tabela e **nunca** executa `ENABLE ROW LEVEL SECURITY`, apesar de a
tabela ter `record_owner_organization_id`. Comparar com
`20260827_0076`, `20260827_0077` e `20260831_0078`, que fazem `ENABLE` + `FORCE`
+ policies.

Estado real do banco:

```text
           relname            | has_owner_col | titan_app_privs
------------------------------+---------------+-----------------
 authorization_grants         | t             |               4
 decision_contestations       | t             |               4
 decision_overrides           | t             |               4
 decision_proposals           | t             |               4
 decision_reviews             | t             |               4
 establishment_qualifications | t             |               4
```

(seis tabelas em `core_audit` com coluna de tenant, RLS desabilitada, e o role
de runtime `titan_app` — `rolsuper=f`, `rolbypassrls=f` — com SELECT/INSERT/
UPDATE/DELETE em todas.)

**Como verifiquei**

`scratchpad/audit/rls_probe.sql`, executado com `SET LOCAL ROLE titan_app` e
`titan.organization_id` = Org 2, contra um grant pertencente inteiramente à
Org 1:

```text
--- ORG 2 reading ORG 1 grants (expected: 0 rows) ---
 44444444-... | 11111111-... | 11111111-... | ATIVO | MARKET_SUPPLY_AGGREGATE_ASSESSMENT
(1 row)

--- ORG 2 revoking ORG 1 grant (expected: 0 rows updated) ---
UPDATE 1

--- ORG 2 deleting ORG 1 grant (expected: 0 rows deleted) ---
DELETE 1

--- ORG 2 reading ORG 1 policies for comparison (RLS-protected table) ---
 org1_policies_visible_to_org2
                             0
```

O controle (`core_audit.policies`, com RLS) devolve `0`, provando que o contexto
de tenant estava corretamente configurado e que a diferença é a ausência de RLS.

**Impacto**

Escalação de privilégio e quebra de isolamento na própria substância da
autorização: uma Organization pode enumerar com quem qualquer outra compartilha
Policy, **revogar** grants alheios (negação de serviço sobre a cadeia comercial
de um concorrente) e **apagar** o registro do grant — destruindo a base de
autorização que o audit de Market Supply referencia por FK. As tabelas
`decision_*` expõem, pelo mesmo mecanismo, propostas, revisões, contestações e
overrides de decisão de outras Organizations.

Este defeito é **anterior** ao Market Supply (introduzido com BuyerPolicy Fase 2,
ADR-0065) e não foi criado pelo Codex nesta rodada. Mas ele invalida a premissa
sobre a qual todo o CUT F está sendo construído.

**Reprodução**

```bash
docker exec -i titan-postgres-1 psql -U titan -d titan -v ON_ERROR_STOP=1 < scratchpad/audit/rls_probe.sql
```

**Comportamento esperado**
`0 rows` na leitura, `UPDATE 0`, `DELETE 0`.

**Comportamento real**
`1 row`, `UPDATE 1`, `DELETE 1`.

**Correção recomendada**
Migration que habilite `ENABLE`/`FORCE ROW LEVEL SECURITY` nas seis tabelas com
policies sobre `record_owner_organization_id`, no padrão de `20260831_0078`.
Para `authorization_grants`, avaliar se o beneficiário precisa de visibilidade
própria (policy adicional por `beneficiary_organization_id`) antes de aplicar,
para não quebrar o fluxo de BuyerPolicy. Adicionar teste de integração no padrão
de `tests/integration/test_organization_postgresql.py` para cada tabela. Adicionar
um teste de **invariante de schema** que falhe quando qualquer tabela com
`record_owner_organization_id` não tiver `relrowsecurity` — isso impede a
reintrodução da classe inteira de defeito.

---

## 6. High Findings

### F-03 — Revogação não bloqueia reexecução idempotente; agregado revogado é reentregue sem audit

```text
Finding ID:   F-03
Severity:     HIGH
Confidence:   HIGH (verificado empiricamente)
```

**Requisito violado**
ADR-0070, seção Revogação, literalmente:

```text
new query -> DENIED
query reexecution -> DENIED
```

ADR-0071 §8 ("Revogacao efetiva bloqueia novas consultas, reexecucoes e novos
relatorios"); SPEC F3, critério de aceite "Revoked grant bloqueia nova consulta
e reexecucao".

**Evidência**

`packages/core_application/idempotency.py:89-105` — em replay, o `handler`
**nunca é chamado**; o `StoredIdempotencyResult` é devolvido verbatim.
`packages/livestock_application/market_supply_workflow.py:342-372` — todo o
gate (autorização, revogação, privacy, audit) vive dentro do handler.
Logo, um replay não reavalia nada e não grava audit.

**Como verifiquei**

`scratchpad/audit/test_audit_revocation_replay.py`:

```text
[REVOKE] 1st execution replayed: False
[REVOKE] 1st payload: ... ["status",["string","RELEASED"]] ...
[REVOKE] audit rows after 1st: 1
[REVOKE] grant revoked_at: 2026-08-28 11:59:00+00:00 status: REVOGADO
[REVOKE] 2nd execution replayed: True
[REVOKE] 2nd payload: ... ["status",["string","RELEASED"]] ...
[REVOKE] audit rows after 2nd: 1
```

O grant está revogado **e** com `status='REVOGADO'` — condição que o
`MarketSupplyAuthorizationService` recusaria por dois motivos independentes — e
ainda assim o agregado de 42 sujeitos é reentregue.

**Impacto**

Um comprador que retenha a idempotency key continua obtendo o agregado depois de
o produtor revogar o consentimento, e esse acesso não deixa rastro de auditoria.
Isso viola simultaneamente a revogação prospectiva e a obrigação de auditar todo
acesso cross-Organization (ADR-0070, seção Auditoria).

**Nota normativa**
`docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md` §9 lista, como gates
obrigatórios simultâneos, "same idempotency key and same semantic digest replays
canonical result" **e** "revoked grant returns uniform `NOT_RELEASED`". Os dois
gates são incompatíveis como escritos e o package não os reconcilia. As ADRs, no
entanto, são explícitas: reexecução após revogação nega. Trato como defeito, não
como questão em aberto.

**Correção recomendada**
Revalidar autorização/revogação antes de servir um replay — por exemplo,
avaliando o grant antes de consultar o store de idempotência, ou invalidando
registros de idempotência associados a um grant revogado. Registrar audit
também no caminho de replay (com `idempotency_reference` e o outcome do
recheck).

---

### F-04 — Release de agregado sem audit durável quando o workflow é construído sem repositório

```text
Finding ID:   F-04
Severity:     HIGH
Confidence:   HIGH (verificado empiricamente)
```

**Requisito violado**
SPEC F3: "Nenhum Market Supply result externamente liberavel existe sem
`CandidatePopulationSnapshot`, `DisclosureDecision` e `MarketSupplyQueryAuditRecord`
duravel." CUT_F3_5 §4: "If durable audit append fails, no public aggregate may be
returned."

**Evidência**

`packages/livestock_application/market_supply_workflow.py:198-207` — o
construtor aceita `audit_repository: ... | None = None` e **o default é None**.
O guarda `market_supply_workflow.py:312-313` só dispara se um repositório foi
injetado:

```python
if self._audit_repository is not None and audit_record is None:
    raise ValueError("audit_record_context e obrigatorio para workflow auditavel.")
```

Já `public_response` (linha 334-337) é sempre mapeado a partir do envelope, sem
qualquer dependência do audit record.

**Como verifiquei**

`scratchpad/audit/test_audit_market_supply_invariants.py::test_C...`:

```text
[AUDIT-C] public status: RELEASED
[AUDIT-C] audit_record: None
[AUDIT-C] aggregate in public payload: {'ready_now': 42}
```

**Impacto**

A invariante "audit-before-release" está implementada como *invariante do objeto
interno* `MarketSupplyAggregateResult`, mas o que sai para o comprador é
`public_response`, que não a respeita. Qualquer wiring que esqueça de injetar o
repositório — o caminho mais fácil, porque é o default — libera dados agregados
sem rastro. Isso é exatamente a condição que a §15 do prompt de auditoria e a
CUT_F3_5 §4 classificam como falha de auditabilidade.

**Comportamento esperado**
Ou o repositório é obrigatório no construtor, ou o mapper de resposta pública
recusa `RELEASE_AGGREGATE` sem `audit_record`.

**Correção recomendada**
Tornar `audit_repository` e `audit_record_context` obrigatórios para qualquer
caminho cujo outcome possa ser `RELEASED`. O default permissivo deveria ser
fail-closed: sem repositório, o outcome máximo é `NOT_RELEASED`.

---

### F-05 — "Recheck de revogação antes do release" é recheck temporal sobre um grant obsoleto

```text
Finding ID:   F-05
Severity:     HIGH
Confidence:   HIGH (evidência de código; ausência estrutural)
```

**Requisito violado**
SPEC F3: "Revogacao deve ser verificada na admissao do workflow e rechecada
antes do release." ADR-0071 §8. Cenário TOCTOU do prompt §13.

**Evidência**

`packages/livestock_application/market_supply_workflow.py:245-248`:

```python
pre_release_authorization = self._authorization_service.assess_aggregate_access(
    request=replace(request.authorization_request, requested_at=request.recorded_at),
    grant=request.grant,
)
```

O recheck reusa **o mesmo objeto `AuthorizationGrant`**, mudando apenas o
instante. `grep` confirma que não existe nenhuma porta de re-leitura de grant em
todo o Market Supply (`GrantRepository|grant_repository|find_grant|load_grant`:
zero ocorrências em `packages/livestock_application/market_supply*.py`).

O teste que dá nome à garantia
(`test_market_supply_workflow.py:839 test_workflow_rechecks_revocation_before_public_release`)
constrói o grant **já com `revoked_at=NOW+30s`** antes da admissão. Ele prova
comparação de timestamps, não observação de estado novo.

**Impacto**

O cenário que a SPEC descreve — `T0 autorização OK / T1 snapshot criada / T2
grant revogado / T3 release` — não é detectado, porque em T3 o workflow ainda
olha o grant lido em T0. O recheck só cobre expiração e revogações cujo
`revoked_at` já era conhecido na admissão.

**Correção recomendada**
Introduzir uma porta de leitura de grant e reler o estado imediatamente antes do
release (ou usar `SELECT ... FOR SHARE` na mesma transação que faz o append do
audit). Substituir o teste por um que mude o estado do grant **entre** admissão
e release.

---

## 7. Medium/Low Findings

### Medium

**F-06 — Contagens de coorte de privacidade não são derivadas da snapshot.**
`AggregationPrivacyInput.organization_count` e `property_count`
(`market_supply_privacy.py:104-105`) são asserções livres do caller. Só
`subject_count` é amarrado (via `current_query.result_subject_count` →
`snapshot.included_count`). Verificado: uma snapshot de **1** Organization passa
o mínimo de 2 porque o caller declarou 3.

```text
[AUDIT-D] snapshot organization_count: 1
[AUDIT-D] snapshot property_count: None
[AUDIT-D] caller asserted organization_count=3 property_count=4
[AUDIT-D] outcome: RELEASED
```

Agravante: `CandidatePopulationSnapshot.internal_universe_summary()`
(`market_supply_population.py:177-186`) **hard-coda** `organization_count` como
`1 if population_size > 0 else 0` e `property_count` como `None` — ou seja, a
snapshot hoje não tem como fornecer os números reais mesmo que o workflow
quisesse derivá-los. Isso torna o piso de coorte por Organization/propriedade
(ADR-0071 §1) não enforceável na composição atual.

**F-07 — Coordenadas temporais do audit não são amarradas às da população.**
`_validate_audit_record_context` (`market_supply_workflow.py:385-409`) valida
digests mas nunca compara `reference_time`/`knowledge_cutoff` com
`snapshot.criteria`. Verificado: população resolvida com cutoff 2026-01-01 é
auditada como 2026-08-28.

```text
[AUDIT-E] snapshot reference_time:  2026-01-01 00:00:00+00:00
[AUDIT-E] audited reference_time:   2026-08-28 12:00:00+00:00
```

Como `knowledge_cutoff` é o critério que o resolver usa para excluir sujeitos
(`_exclusion_reason` → `NOT_KNOWN_AT_CUTOFF`), um audit com coordenadas
divergentes descreve incorretamente o que era conhecido — degradando justamente
a distinção "o que era verdadeiro em T" vs "o que era conhecido em T" que a
ADR-0071 §5 quer preservar.

**F-08 — `aggregate_payload` não tem schema nem allow-list.**
É `Mapping[str, Any]` do caller até a resposta pública
(`market_supply_response.py:52-70`), sem validação. O critério de aceite da
SPEC F3 "Nenhum ID individual aparece no payload buyer-facing" existe apenas
como texto; nada no código o impede.

**F-09 — `audit_owner_organization_id` é fornecido pelo caller e não validado.**
`MarketSupplyAggregateGateRequest.__post_init__` valida a coerência de policy,
fingerprint, snapshot e audit context, mas nunca valida
`audit_owner_organization_id` contra o owner ou o beneficiário. Como a RLS da
tabela é `record_owner_organization_id = current_setting('titan.organization_id')`,
o valor errado torna o registro invisível ao contexto que precisa lê-lo — ou o
insert falha na policy de INSERT. Relacionado: o teste de integração
(`test_market_supply_query_audit_postgresql.py:103-114`) demonstra que sob o
contexto do **comprador** a busca de histórico relacionado devolve `()`. Se o
endpoint futuro rodar sob o contexto do comprador (como o gate package propõe,
"buyer/requester Organization is the active Organization context"), o histórico
de differencing será vazio por RLS — uma **segunda** causa independente de F-01.
Decidir a propriedade do registro de audit é um pré-requisito de F3.5.

**F-10 — `pytest` sem `TITAN_DATABASE_URL` pula 285 testes em silêncio, incluindo todos os de RLS/isolamento.**
`CLAUDE.md` afirma: "Os testes de integração leem `TITAN_DATABASE_URL`; sem ela,
usam o PostgreSQL local do `compose.yaml` por padrão." Isso não acontece:
`tests/integration/conftest.py:29-33` simplesmente pula. Medido:

```text
sem  TITAN_DATABASE_URL: 1277 passed, 286 skipped
com  TITAN_DATABASE_URL: 1562 passed,   1 skipped
```

Uma execução "verde" do portão de verificação documentado no `CLAUDE.md`
**não exercita nenhuma prova de isolamento multi-tenant**. Isso é um risco de
processo: é assim que F-02 pôde persistir. Ou o fallback prometido é
implementado, ou o conftest deve falhar (não pular) quando a variável está
ausente.

### Low

**F-11 — `TransactionalAuthorizationGrantRepository.revoke()` zera `revocation_reason`.**
`packages/core_infrastructure/persistence/authorization_grant.py:165-186` faz
`revocation_reason = NULL` incondicionalmente, sem aceitar um motivo. Perde
material de auditoria em uma tabela que já é `PROTECTED`.

**F-12 — Desempate arbitrário por UUID na seleção de Decision divergente (CUT C).**
`packages/livestock_application/market_readiness.py:408-419` ordena candidatos
por `str(decision_id.value)` e pega o primeiro. É determinístico mas
semanticamente arbitrário: o critério não é recência nem relevância. Quando há
múltiplas Decisions divergentes, qual delas é apresentada ao usuário depende de
ordenação de UUID. O outcome permanece `REASSESSMENT_REQUIRED`, então o impacto
é sobre qual evidência é exibida, não sobre a conclusão.

**F-13 — Fronteira semiaberta em `sanitary_test_coverage.py` exclui tratamento exatamente em `reference_time`.**
A mudança `<=` → `<` (linhas 144, 192, 215) é consistente com a convenção
`[from, until)` já usada pelo serviço dimensional
(`dimensional_coverage.py:169`), então não é uma regressão de consistência.
Mas a direção é permissiva para um predicado sanitário: um tratamento
antimicrobiano administrado exatamente em `reference_time` deixa de contar em
`has_antimicrobial_treatment`. Aplica-se apenas à Policy fictícia
`SANITARY_TEST_A_v1`, o que limita o impacto. Registro como observação de
semântica de domínio a confirmar com o Product Owner, não como defeito.

### Info

- Disciplina de escopo é real e verificável: nenhum endpoint, nenhuma leitura
  cross-tenant, nenhum Aggregate Root de `CommercialDemand`, nenhum
  `SupplyForecast`, nenhuma mudança em Dossier/VerificationBundle.
- Fronteiras de pacote limpas: zero `domain -> infrastructure`, zero conceito de
  Market Supply em `core_domain`/`core_application`/`shared_kernel`/`core_integrity`.
- `ruff`, `mypy` (677 arquivos) e `alembic check` limpos.

---

## 8. Market Supply Audit

### ADR-0069 — análise não regulatória

**PASS.** `CommercialDemandContext` é transitório e frozen. Nenhum
`SupplyForecast`, `SupplyDemandAnalysis` ou `SupplyIntelligenceReport`
persistido. Nenhuma linguagem de certificação. `ProducerMarketSupplyAnalysis`
carrega `PRODUCER_SIDE_SINGLE_ORGANIZATION_ANALYSIS` e
`MARKET_ELIGIBILITY_RESULT_BOUNDARY` explicitamente. Sem ML/IA. Core não
absorveu o conceito vertical.

### ADR-0070 — progressive disclosure

**PARTIAL.** Purposes separados: PASS. Ausência de grant nega: PASS. Resposta
uniforme na aplicação: PASS. Differencing/repeated-query: **FAIL** (F-01).
Revogação de reexecução: **FAIL** (F-03). Auditoria obrigatória de todo acesso
cross-Organization: **FAIL** (F-03, F-04). Reuso de Core Authorization: PASS —
mas o substrato reusado está sem RLS (F-02).

### ADR-0071 — production gates

| Gate | Estado |
| --- | --- |
| §1 Privacy profile versionado | PARTIAL — mecanismo existe, sem valores produtivos aprovados (correto), mas os pisos de Organization/propriedade não são enforceáveis (F-06) |
| §2 Audit/query persistence | PASS na persistência; FAIL na cobertura (F-03, F-04) |
| §3 Resolver aprovado, sem lookup global | PASS — resolver in-memory, sem acesso a rebanho; `organization_count`/`property_count` da snapshot são placeholders (F-06) |
| §4 Snapshot/digest linkage | PASS para `MarketSupplyAggregateResult`; FAIL para `public_response` (F-04) |
| §4B DisclosureDecision | PASS — VO imutável, distinto de authorization e de Evaluation/Decision |
| §5 Idempotência semântica | PASS na identidade; FAIL na interação com revogação (F-03) |
| §6 Rate limit + differencing semântico | **FAIL** (F-01) |
| §7 Uniform public behavior | PASS na aplicação; UNKNOWN em HTTP/status/cache/timing (não existe camada HTTP) |
| §8 Revogação | PARTIAL — nova consulta bloqueada; reexecução não (F-03); recheck é temporal (F-05) |
| §9 CommercialDemand transitório | PASS |

### F3 status

O endpoint `POST /v1/livestock/market-supply/aggregate-assessments` **não
existe** — corretamente, porque o HUMAN RELEASE GATE de F3.5 não foi aprovado.
`docs/plans/CUT_F3_5_MARKET_SUPPLY_RELEASE_GATE_PACKAGE.md` é um bom documento
de gate. Meu alerta: ele lista, entre os "Required Automated Gates", itens que
minha verificação mostra **já não satisfeitos** hoje (differencing, revogação de
reexecução, audit em todos os resultados). Se o gate for avaliado contra os
testes existentes, ele passará indevidamente.

---

## 9. Tenant Isolation Audit

### Testes executados

| Teste | Método | Resultado |
| --- | --- | --- |
| RLS de `market_supply_query_audit_records` | Role `NOBYPASSRLS` com GRANT de SELECT/INSERT/UPDATE/DELETE; leitura sob outra Organization | **PASS** — `get()` retorna `None`, `find_related_query_fingerprints()` retorna `()` |
| Append-only de `market_supply_query_audit_records` | `UPDATE`/`DELETE` sob role sem bypass | **PASS** — `rowcount == 0` em ambos; registro intacto |
| Duplicidade de `audit_id` | Segundo `append` do mesmo registro | **PASS** — `IntegrityError` |
| RLS de `authorization_grants` | Sonda própria: role `titan_app`, contexto Org 2, alvo Org 1 | **FAIL** — SELECT 1 row, UPDATE 1, DELETE 1 |
| Controle da sonda (`core_audit.policies`) | Mesma sessão, mesma Org | **PASS** — 0 rows (confirma que o contexto de tenant estava correto) |
| Varredura de schema | `pg_class.relrowsecurity` vs presença de `record_owner_organization_id` | **FAIL** — 6 tabelas tenant-scoped sem RLS |
| Population resolver cross-tenant | `_exclusion_reason` com sujeito de outra Organization | **PASS** — `ORGANIZATION_MISMATCH` |
| Vazamento por resposta pública | Todos os não-releases | **PASS** na aplicação — `{"status": "NOT_RELEASED"}` idêntico |
| Vazamento por inferência agregada | Subtração de coorte | **FAIL** (F-01) |

### Inferência lateral

Testei os vetores da §7 do prompt. `counts`, `HTTP status`, `errors`,
`pagination` e `timing` não são avaliáveis porque não existe camada HTTP.
`uniqueness conflicts` está coberto no nível de aplicação (todos os motivos
internos colapsam para `NOT_RELEASED`). O vetor que **está** aberto é o de
agregação/differencing (F-01), que é precisamente o que a ADR-0071 §6 exige
fechar antes da primeira API.

---

## 10. Temporal Integrity Audit

- `reference_time` e `knowledge_cutoff` são obrigatórios e validados como UTC em
  `CandidatePopulationCriteria`, `MarketSupplyRequestIdentity`,
  `MarketSupplyAuditRecordContext` e `MarketSupplyQueryAuditRecord`. **PASS.**
- Ambos entram no `semantic_digest()`, então reexecução com coordenadas
  diferentes é query semanticamente distinta e gera `IdempotencyConflict` com a
  mesma chave. **PASS** — corresponde a ADR-0071 §5.
- `knowledge_cutoff` é efetivamente usado pelo resolver: sujeitos com
  `known_at > knowledge_cutoff` são excluídos como `NOT_KNOWN_AT_CUTOFF`
  (`market_supply_population.py:249-250`), preservando "o que era conhecido em T".
  **PASS.**
- **Gap (F-07):** as coordenadas do audit não são amarradas às da snapshot. Um
  registro histórico pode declarar coordenadas que não descrevem a população que
  foi de fato resolvida. Isso não reescreve decisão histórica (o registro é
  append-only), mas permite que ela seja gravada incorretamente na origem.
- Correções tardias não reescrevem decisões históricas: a tabela é append-only e
  o `record_digest` cobre todos os campos. **PASS.**

---

## 11. Audit and Evidence Integrity

- **Append-only:** aplicado por RLS (`FORCE`, sem policy de UPDATE/DELETE),
  verificado com role sem bypass. **PASS.**
- **Integridade:** `record_digest()` canônico via `CanonicalSerializer` +
  `canonicalize_for_hash`, cobrindo todos os campos incluindo o fingerprint;
  índice único sobre `record_digest`. **PASS.**
- **Atomicidade:** `TransactionalMarketSupplyQueryAuditRepository` opera sobre a
  `Connection` do chamador, então o append participa da transação do caso de uso.
  **PASS.**
- **Minimização:** apenas digests, counts e reason codes. Nenhum ID de sujeito,
  nenhum payload sensível. `population_digest` é hash da lista de IDs, não a
  lista. **PASS** — bem executado.
- **Correlação:** `correlation_id`, `idempotency_reference`,
  `semantic_request_digest`, `grant_id` presentes e indexados. **PASS.**
- **Falha de audit:** com repositório injetado, a exceção do `append` propaga e
  nenhuma resposta é mapeada (`test_audit_append_failure_blocks_public_response_mapping`).
  **PASS** nesse caminho; **FAIL** no caminho sem repositório (F-04).
- **Cobertura:** não cobre replay idempotente (F-03).
- **Dossier / VerificationBundle / verificação offline:** nenhum arquivo de
  `core_integrity` foi tocado; a suíte completa passa. Nenhuma regressão
  detectada. **PASS.**

---

## 12. Database / Migration Review

**Migration `20260831_0078` — qualidade alta.**

- Upgrade e downgrade simétricos; downgrade dropa policies, índices e tabela na
  ordem correta.
- FKs para `organizations` (×3), `policies` e `authorization_grants`.
- 17 `CheckConstraint`, incluindo três **acoplados**, que codificam invariantes
  de domínio no schema (e não só na aplicação):
  - `outcome='RELEASED' ⟺ external_disposition='RELEASE_AGGREGATE'`
  - `outcome='RELEASED' ⟺ result_digest IS NOT NULL`
  - `population_digest IS NOT NULL OR outcome <> 'RELEASED'`
  Isso é enforcement real, não documentação. Bom trabalho.
- 8 índices, incluindo dois parciais (`WHERE ... IS NOT NULL`) e um cobrindo
  exatamente o padrão de query do differencing.
- `ENABLE` + `FORCE ROW LEVEL SECURITY`, policies só de SELECT e INSERT,
  `REVOKE ALL ... FROM PUBLIC`.
- Comentário de classificação `titan.classification=PROTECTED`.
- Registrada em `env.py` com a asserção de metadata do padrão do repositório.
- `alembic check`: sem drift entre ORM e schema.

**Problema:** `5e402311b352_create_authorization_grants_table_for_.py` é uma
migration autogerada que nunca foi ajustada — sem RLS, sem check constraints,
sem índices além da PK, com o comentário `# ### commands auto generated by
Alembic - please adjust! ###` ainda no corpo. É a origem de F-02. O diff não
commitado apenas reformata esse arquivo (aspas e indentação); não corrige a
ausência de RLS.

---

## 13. Test Quality Assessment

A suíte é grande (1562 testes) e passa integralmente com PostgreSQL. Mas a
pergunta relevante é: **ela detectaria uma regressão séria?** Apliquei o teste
de mutação conceitual da §23.

| Se eu remover/inverter... | Algum teste falharia? |
| --- | --- |
| Filtro de Organization no resolver | Sim — `test_market_supply_population.py` |
| RLS de `market_supply_query_audit_records` | Sim — teste de integração (só com `TITAN_DATABASE_URL`) |
| Exigência de `result_digest` para release | Sim — invariante em `__post_init__` + check constraint |
| Linkage snapshot ↔ fingerprint ↔ audit | Sim — vários testes de ValueError |
| Uniformidade de `NOT_RELEASED` | Sim — `test_privacy_suppression_keeps_public_response_uniform` |
| Conflito de idempotência | Sim |
| **A avaliação de differencing inteira** | **Não** — já está inerte e a suíte é verde |
| **A obrigatoriedade de audit no release** | **Não** — o caminho sem repositório já libera sem audit |
| **A negação por revogação em reexecução** | **Não** — nunca foi implementada |
| **Os pisos de coorte por Organization/propriedade** | **Não** — são asserções do caller |
| **RLS de `authorization_grants`** | **Não** — nunca existiu |

**Padrões problemáticos identificados:**

1. **Teste que reproduz a implementação em vez do contrato.**
   `test_workflow_uses_audit_history_for_differencing_before_release` monta um
   estado inatingível (mesma snapshot, filtros diferentes) para exercitar
   `_has_differencing_risk`. Passa, e dá confiança falsa em um controle inerte.
   É o caso mais grave da suíte.

2. **Teste cujo nome promete mais do que o corpo verifica.**
   `test_workflow_rechecks_revocation_before_public_release` passa um grant já
   revogado na construção — verifica comparação de timestamps, não recheck de
   estado.

3. **Ausência de testes negativos sobre entradas assertivas.** Nada testa
   `organization_count` inconsistente com a snapshot, coordenadas temporais
   divergentes, ou `aggregate_payload` contendo IDs.

4. **Configuração padrão esconde a camada de testes mais importante.** F-10:
   285 testes, incluindo todo o isolamento multi-tenant, pulam em silêncio.

**Pontos fortes reais:** os testes de integração PostgreSQL são honestos — criam
role `NOBYPASSRLS`, concedem explicitamente os privilégios que querem provar
bloqueados, e verificam `rowcount == 0`. Esse é o padrão certo e deveria ser
replicado para as seis tabelas de F-02.

**Nenhum** teste `skip`/`xfail` mascarando falha foi encontrado: os 286 skips têm
todos a mesma causa ambiental.

---

## 14. Scope Drift / Premature Architecture

| Item | Classificação | Nota |
| --- | --- | --- |
| Migration + tabela de audit criadas no CUT F3 | **JUSTIFIED** | ADR-0071 §2 exige persistência de audit como gate produtivo; a SPEC F3 autoriza schema design e a migration futura sob aceite de schema/RLS/retention, que o CUT_F3_4 documenta |
| Repositório transacional em `livestock_infrastructure` | **JUSTIFIED** | Tabela em `core_audit` (material protegido), adapter na vertical (conceito Livestock) — coerente com ADR-0069 |
| `CommercialDemandContext` transitório | **BENIGN** | Exatamente a recomendação da ADR-0071 §9 |
| Ausência de endpoint | **JUSTIFIED** | Respeita o HUMAN RELEASE GATE de F3.5 |
| ~25 documentos de plano/relatório não commitados | **QUESTIONABLE** | Volume documental grande fora de `docs/CHECKLIST_DE_IMPLEMENTACAO.md`; o `CLAUDE.md` pede que nenhuma trilha paralela de plano/progresso exista sem consolidação. O checklist **foi** atualizado, então a regra é respeitada na letra; o risco é de dispersão |
| `apps/validacao/market_supply_synthetic.py` | **BENIGN** | Script sintético, sem dados reais, coerente com CUT F0 |

**Nenhuma VIOLATION de escopo identificada.** Este é um ponto genuinamente forte
do trabalho: a tentação de construir o endpoint foi resistida.

---

## 15. Production Readiness

| Capability | Classificação | Justificativa |
| --- | --- | --- |
| Producer-side Market Supply analysis (F1) | **INTEGRATED** | Compõe `MarketReadiness` existente; sem persistência nem API, por decisão |
| Candidate Population resolver/snapshot | **IMPLEMENTED_IN_MEMORY** | Determinístico e testado, mas opera sobre sujeitos fornecidos pelo caller; `organization_count`/`property_count` são placeholders |
| Authorization (purpose/scope) | **VERIFIED** na lógica, **PROTOTYPE** na composição | O serviço está correto; o substrato de persistência dos grants está sem RLS (F-02) e não há porta de re-leitura (F-05) |
| DisclosureDecision | **IMPLEMENTED_IN_MEMORY** | VO imutável correto e bem separado de authorization |
| Aggregation privacy (cohort/geo/filters) | **PROTOTYPE** | Mecanismo existe; pisos de Organization/propriedade não enforceáveis (F-06); valores produtivos corretamente não aprovados |
| Semantic differencing | **DESIGN_ONLY** | Código presente porém inalcançável na composição (F-01) |
| Market Supply query audit (persistência) | **PERSISTED / VERIFIED** | Migration, RLS, append-only e digest canônico provados em PostgreSQL |
| Audit coverage (todos os resultados) | **PROTOTYPE** | Lacunas em replay e no caminho sem repositório (F-03, F-04) |
| Idempotência semântica | **INTEGRATED** | Correta; interação com revogação em aberto (F-03) |
| Revogação | **PROTOTYPE** | Nova consulta bloqueada; reexecução não; recheck é temporal |
| Uniform public behavior | **IMPLEMENTED_IN_MEMORY** | Aplicação uniforme; HTTP/status/cache/timing inexistentes |
| Aggregate API cross-tenant (F3.5) | **NOT_STARTED** | Correto — bloqueado por HUMAN GATE |
| Dossier / VerificationBundle | **PRODUCTION_READY** (inalterado) | Nenhuma regressão detectada nesta rodada |

---

## 16. Recommended Actions

### P0 — antes de continuar ou expor qualquer superfície

1. **Habilitar RLS nas seis tabelas tenant-scoped de `core_audit`** (F-02):
   `authorization_grants`, `decision_proposals`, `decision_reviews`,
   `decision_overrides`, `decision_contestations`,
   `establishment_qualifications`. Migration no padrão de `20260831_0078`, com
   teste de integração por tabela usando role `NOBYPASSRLS`. Definir antes se
   `authorization_grants` precisa de policy adicional por
   `beneficiary_organization_id` para não quebrar BuyerPolicy.
2. **Adicionar teste de invariante de schema** que falhe quando qualquer tabela
   com `record_owner_organization_id` não tiver `relrowsecurity` — impede a
   reintrodução da classe inteira de defeito.
3. **Corrigir a chave de correlação do differencing** (F-01): desacoplar o eixo
   de agrupamento do histórico do `snapshot_digest`. Adicionar o teste de
   subtração de coorte usando o `CandidatePopulationResolver` real.
4. **Fazer o portão de verificação exercitar PostgreSQL** (F-10): implementar o
   fallback prometido no `CLAUDE.md` ou fazer o conftest falhar, em vez de pular,
   quando a variável está ausente.

### P1 — antes do próximo corte arquitetural (F3.3/F3.4/F3.5)

5. Tornar audit obrigatório em qualquer caminho que possa resultar em `RELEASED`
   (F-04) — fail-closed por default.
6. Resolver a colisão entre replay idempotente e revogação (F-03), incluindo
   audit do caminho de replay.
7. Introduzir porta de re-leitura de grant e recheck de estado antes do release
   (F-05); substituir o teste correspondente.
8. Derivar `organization_count`/`property_count` da `CandidatePopulationSnapshot`
   (F-06) — o que exige que a snapshot passe a carregar esses números de verdade.
9. Amarrar `reference_time`/`knowledge_cutoff` do audit aos da snapshot (F-07).
10. Decidir e validar a propriedade do registro de audit (F-09) antes de
    especificar o contexto de Organization do endpoint.

### P2 — agendar em breve

11. Definir schema/allow-list para `aggregate_payload` (F-08), com teste que
    rejeite chaves não previstas.
12. Revisar os "Required Automated Gates" do CUT_F3_5 contra os achados deste
    relatório antes de submetê-los à aprovação humana.
13. Commitar o CUT F. Manter ~2.900 linhas de código de segurança e ~25
    documentos fora do controle de versão é risco operacional próprio.

### P3 — melhoria

14. `revoke()` deve aceitar e preservar `revocation_reason` (F-11).
15. Trocar o desempate por UUID por um critério de domínio explícito em
    `MarketReadinessPopulationReader` (F-12).
16. Confirmar com o Product Owner a direção da fronteira semiaberta em
    `has_antimicrobial_treatment` (F-13).

---

## 17. Human Decisions Actually Required

Apenas duas decisões são genuinamente normativas e não redutíveis a correção
técnica:

1. **Precedência entre replay idempotente e revogação.** As ADRs 0070/0071 dizem
   que reexecução após revogação nega; o Release Gate Package exige replay
   canônico da mesma chave. Tecnicamente ambos são implementáveis; qual vence é
   escolha de produto/privacidade. *Minha leitura das ADRs é que revogação vence*
   — mas a contradição está escrita e precisa ser resolvida no documento, não só
   no código.

2. **Propriedade do `MarketSupplyQueryAuditRecord`.** Produtor (owner), comprador
   (requester), ou ambos via policy dupla. A escolha determina se o histórico de
   differencing é legível sob o contexto de Organization do endpoint, e portanto
   é pré-requisito de F3.5 (ver F-09). ADR-0071 §2 deixou explicitamente em
   aberto ("RLS protegendo buyer/requester e owner/audit visibility conforme
   decisao do plano tecnico").

As decisões já listadas como pendentes pela própria ADR-0071 (valores do privacy
profile, retenção do audit, contrato HTTP/cache/timing, fontes do resolver,
permission name) permanecem legitimamente em aberto e **não** são reclassificadas
aqui como defeito.

---

## 18. Final Verdict

```text
HOLD_EXPOSURE
```

O desenvolvimento interno pode e deve continuar. Nenhuma superfície externa de
Market Supply pode ser liberada no estado atual, e o item P0-1 deve ser tratado
imediatamente por ser independente do Market Supply.

**Justificativa objetiva:**

- Existe uma quebra de isolamento entre Organizations **já ativa em produção
  local**, verificada empiricamente com o role de runtime real (F-02). Ela não
  foi introduzida pelo CUT F, mas invalida a premissa de autorização sobre a
  qual o CUT F está sendo construído. Isso sozinho justifica ação imediata.
- Dois dos controles que a ADR-0071 nomeia como pré-condição da primeira API
  agregada — differencing semântico e negação de reexecução após revogação —
  não existem de fato, apesar de existirem em código e em relatório (F-01, F-03).
- A invariante "nenhum result liberável sem audit durável" tem um caminho de
  bypass que é o comportamento **default** do construtor (F-04).
- Contra isso: não há endpoint, não há leitura cross-tenant, o escopo foi
  respeitado com rigor incomum, a persistência de audit é sólida e bem provada,
  e nada em Dossier/VerificationBundle regrediu. O sistema não está em estado
  perigoso para continuar construindo — está em estado perigoso para **expor**.

**Respondendo às perguntas da §45:**

- *O Titan implementado corresponde ao arquitetado?* Estruturalmente sim;
  em três garantias de privacidade/autorização, não.
- *As garantias declaradas existem ou apenas parecem existir?* Differencing,
  negação de reexecução e audit-before-release **parecem** existir. As demais
  existem.
- *Os testes detectariam uma regressão séria?* Para linkage, uniformidade e
  append-only, sim. Para differencing, revogação em replay e RLS de grants, não —
  porque esses controles nunca funcionaram e a suíte é verde.
- *Há caminho de bypass das invariantes?* Sim: workflow sem repositório (F-04) e
  replay idempotente (F-03).
- *O isolamento entre Organizations está preservado?* Não na tabela de grants e
  em mais cinco tabelas de `core_audit`.
- *Market Supply pode revelar informação por agregação/differencing?* Sim,
  demonstrado com subtração de coorte.
- *O histórico continua verificável e temporalmente correto?* Sim, com a ressalva
  de F-07 (coordenadas do audit não amarradas à população).
- *O Codex está seguindo o escopo?* Sim, com disciplina notável.
- *Podemos continuar com confiança?* Com os P0 endereçados, sim.

---

## Anexo — Artefatos temporários de auditoria

Criados fora do repositório, em
`C:\Users\prmon\AppData\Local\Temp\claude\D--projects-Titan\fbf10686-913f-4655-9a4e-e8659408069e\scratchpad\audit\`.
Nenhum código de produção foi alterado durante esta auditoria.

| Arquivo | O que prova |
| --- | --- |
| `test_audit_market_supply_invariants.py` | F-01 (A, B), F-04 (C), F-06 (D), F-07 (E) — 5 testes, todos falham contra o estado atual |
| `probe_history.py` | F-01: histórico entregue ao privacy service é sempre 0 fingerprints |
| `test_audit_revocation_replay.py` | F-03: replay após revogação devolve o agregado RELEASED sem audit |
| `rls_probe.sql` | F-02: SELECT/UPDATE/DELETE cross-tenant em `authorization_grants` sob `titan_app` |

Comandos usados:

```bash
PYTHONPATH=. .venv/Scripts/python.exe -m pytest scratchpad/audit/ -q -s
```

```bash
docker exec -i titan-postgres-1 psql -U titan -d titan -v ON_ERROR_STOP=1 < scratchpad/audit/rls_probe.sql
```

Recomendo promover os cinco testes de invariante para `tests/audit/` (ou
`tests/security/`) **depois** das correções P0/P1, para que passem a proteger as
propriedades em vez de documentar sua ausência.
