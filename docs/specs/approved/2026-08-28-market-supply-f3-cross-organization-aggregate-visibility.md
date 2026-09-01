# SPEC: Market Supply F3 - Cross-Organization Aggregate Visibility

- **Nível:** CRITICAL
- **Estado:** PROCEED WITH CHANGES para plano oficial; BUILD requer confirmacao explicita
- **Decisão de Discovery:** PROCEED apos ADR-0071 ACCEPTED WITH CHANGES
- **Owner de produto:** Founder / Product Owner
- **Data:** 2026-08-28

## Problema e usuário

Compradores/frigorificos precisam consultar capacidade agregada autorizada sem receber automaticamente identidade de produtores, propriedades, animais, tratamentos, Evidence, Dossier ou VerificationBundle. Produtores precisam controlar contribuicao de dados e preservar privacidade mesmo quando autorizam participacao em Market Supply.

F0-F2H ja provaram componentes em memoria. ADR-0071 aceitou os gates produtivos que devem existir antes da primeira superficie buyer-facing.

## Contexto e objetivo

F3 deve entregar a menor superficie produtiva de visibilidade agregada cross-Organization:

- request buyer-facing com contexto comercial transitorio;
- resolucao de populacao apenas sobre fontes autorizadas;
- snapshot/digest canonico da populacao;
- disclosure decision separado de authorization;
- privacy/differencing antes de release;
- aggregate result ligado a snapshot, disclosure decision e audit;
- resposta publica uniforme quando nao houver disclosure;
- auditoria persistente suficiente para historico, idempotencia e differencing.

## Fora de escopo

- persistir `CommercialDemand` como Aggregate Root;
- `SupplyForecast`;
- `SupplyDemandAnalysis` com capacidade futura;
- `SupplyIntelligenceReport` persistido/hashable;
- disclosure de produtor/propriedade/grupo/animal;
- Evidence, Dossier ou VerificationBundle sharing;
- exportacao CSV/PDF/API extraction;
- integracao MAPA/IAGRO/SISBOV;
- ML/IA;
- marketplace, reserva, pagamento, contrato comercial ou ERP de compras.

## Comportamento e regras de negócio

F3 opera no purpose `MARKET_SUPPLY_AGGREGATE_ASSESSMENT`.

Fluxo obrigatorio:

```text
CommercialDemandContext transitorio
        |
        v
Canonicalization / MarketSupplyRequestIdentity
        |
        v
Authorization / opt-in grants
        |
        v
CandidatePopulationCriteria
        |
        v
CandidatePopulationSnapshot
        |
        v
QueryFingerprint
        |
        v
Historical Query Relationship Assessment
        |
        v
DisclosureDecision
        |
        +--> NOT_RELEASED uniforme
        |
        v
AggregateResult
        |
        v
MarketSupplyQueryAuditRecord
        |
        v
UniformPublicResponse
```

Invariantes:

- `reference_time` e `knowledge_cutoff` sao obrigatorios.
- Reexecucao com `reference_time` ou `knowledge_cutoff` diferentes e query semanticamente distinta.
- Autorizacao para contribuir nao implica inclusao em todo agregado.
- `DisclosureDecision` pode `ALLOW`, `GENERALIZE`, `SUPPRESS` ou `DENY`.
- Nenhum Market Supply result externamente liberavel existe sem `CandidatePopulationSnapshot`, `DisclosureDecision` e `MarketSupplyQueryAuditRecord` duravel.
- Resultado publico liberado nao expoe IDs individuais nem membership.
- `NOT_RELEASED` nao revela se a causa foi inexistencia, invisibilidade, exclusao, autorizacao, privacy suppression ou differencing.
- Revogacao efetiva bloqueia novas consultas e reexecucoes.
- Revogacao deve ser verificada na admissao do workflow e rechecada antes do release.
- CommercialDemand e contexto transitorio nesta versao.

## Contrato público mínimo proposto

Endpoint proposto para BUILD F3:

```text
POST /v1/livestock/market-supply/aggregate-assessments
```

Headers:

- Organization ativa = buyer/requester Organization.
- Idempotency key obrigatoria, usando mecanismo Core existente.

Request body conceitual:

```json
{
  "policy_id": "uuid",
  "policy_version_id": "uuid-or-null-if-current-resolution-approved",
  "purpose": "MARKET_SUPPLY_AGGREGATE_ASSESSMENT",
  "quantity": 8000,
  "commercial_window": {
    "from": "2026-09-01T00:00:00Z",
    "until": "2026-10-15T00:00:00Z"
  },
  "reference_time": "2026-08-28T00:00:00Z",
  "knowledge_cutoff": "2026-08-28T00:00:00Z",
  "candidate_criteria": {
    "subject_type": "animal",
    "authorized_network_id": "opaque-or-null",
    "required_tags": ["synthetic-or-approved-filter"],
    "geography": {
      "state": "MS"
    }
  }
}
```

Released response conceitual:

```json
{
  "status": "RELEASED",
  "assessment_id": "uuid",
  "generated_at": "2026-08-28T12:00:00Z",
  "reference_time": "2026-08-28T00:00:00Z",
  "knowledge_cutoff": "2026-08-28T00:00:00Z",
  "policy_id": "uuid",
  "policy_version_id": "uuid",
  "population_digest": "sha256:...",
  "disclosure_decision": "ALLOW",
  "aggregate": {
    "subjects_considered": 12430,
    "ready": 7820,
    "conditioned": 1210,
    "indeterminate": 910,
    "not_ready": 1640,
    "not_evaluated": 850,
    "estimated_shortage": 180
  },
  "limitations": []
}
```

Not released response conceitual:

```json
{
  "status": "NOT_RELEASED",
  "assessment_id": "uuid",
  "generated_at": "2026-08-28T12:00:00Z"
}
```

O contrato HTTP final, status code, cache, timing padding e pagination exigem revisao no BUILD plan antes da implementacao.

## Plano técnico

### Application/domain value objects

Adicionar, preferencialmente em `packages/livestock_application`:

- `CommercialDemandContext` transitorio;
- `MarketSupplyRequestIdentity`;
- `DisclosureDecision`;
- `MarketSupplyAggregateResult`;
- `MarketSupplyQueryAuditRecord`;
- repositorio/porta para audit query persistence;
- production profile object para `AggregationPrivacyPolicy`;
- application service F3 que compoe os componentes F2B-F2H.

Nao criar Aggregate Root para CommercialDemand.

### Persistence

Design de schema permitido antes do BUILD:

- schema proposal;
- indexes;
- unique constraints;
- FKs;
- RLS model;
- retention proposal;
- expected query patterns.

Migration futura proposta, bloqueada ate aceite de schema/RLS/retention:

- `core_audit.market_supply_query_audit` ou schema equivalente ja usado para auditoria protegida;
- append-only por politica de grants/RLS, sem UPDATE/DELETE para runtime;
- RLS protegendo buyer/requester e owner/audit visibility conforme decisao do plano tecnico;
- colunas para os campos minimos da ADR-0071.

Persistir payload sensivel bruto e proibido. Persistir digests, counts internos e reason codes auditaveis e permitido quando necessario.

O audit deve registrar tambem queries que nao chegam a agregacao: `AUTHORIZATION_DENIED`, `PURPOSE_MISMATCH`, `GRANT_REVOKED`, `POPULATION_SUPPRESSED`, `DIFFERENCING_BLOCKED`, `PRIVACY_DENIED`, `GENERALIZED` e `RELEASED`.

### Candidate Population resolver

Primeiro F3 deve usar fonte autorizada explicita e limitada:

- grants/opt-in existentes ou novo corte de participation aprovado;
- MarketReadiness read model;
- dados Livestock apenas da Organization owner sob contexto autorizado;
- nenhum lookup global.

Se o repo ainda nao tiver opt-in/grant suficiente para resolver rede autorizada, BUILD deve parar em HUMAN GATE antes de criar acesso cross-tenant.

### Privacy/disclosure

`AggregationPrivacyPolicy` produtiva precisa de profile versionado. O primeiro profile deve ser configuravel em codigo/config apenas se aprovado como reversible deployment profile; valores numericos concretos exigem revisao.

`DisclosureDecision` deve ser produzido antes de qualquer aggregate result publico.

DisclosureDecision pode depender da query atual e de queries anteriores semanticamente relacionadas. O BUILD deve tratar semantic differencing como etapa propria ou como subservico formal de privacy/disclosure, antes da decisao final.

### Idempotency

Usar `IdempotencyService` Core antes da resolucao de populacao. A aplicacao deve construir `MarketSupplyRequestIdentity` e `semantic_request_digest` com:

- buyer Organization;
- purpose;
- policy_id/policy_version_id;
- demand/context digest;
- candidate criteria digest;
- reference_time;
- knowledge_cutoff;
- idempotency key.

Mesmo idempotency key com mesmo semantic digest retorna replay canonico. Mesmo idempotency key com semantic digest diferente retorna `IDEMPOTENCY_CONFLICT`.

### API

Adicionar rota somente apos os pontos acima estarem implementados:

- autentica principal;
- resolve OrganizationContext;
- exige permission de Market Supply agregada ou capability equivalente existente;
- executa service sob transacao;
- retorna shape uniforme.

F3.5 exige HUMAN RELEASE GATE proprio depois de F3.1-F3.4 estarem tecnicamente aceitos.

### Validation script

Criar roteiro em `apps/validacao/market_supply_f3_aggregate.py` quando houver endpoint:

- sobe ambiente;
- descobre Organizations e entidades sem copiar IDs;
- cria/semeia dados ficticios;
- mostra request/response;
- prova release agregado;
- prova `NOT_RELEASED` por ausencia/revogacao/privacy sem revelar motivo ao comprador;
- prova audit interna.

## Critérios de aceite

- Endpoint retorna apenas agregado ou `NOT_RELEASED` uniforme.
- Nenhum ID individual aparece no payload buyer-facing.
- Authorization precede population resolution.
- Snapshot precede disclosure decision.
- Disclosure decision precede aggregate result.
- Audit record existe para authorization denied, purpose mismatch, grant revoked, population suppressed, differencing blocked, privacy denied, generalize e release.
- Revoked grant bloqueia nova consulta e reexecucao.
- Grant valido na admissao e revogado antes do disclosure gera `NOT_RELEASED` e audit com revogacao observada.
- Idempotency retorna mesmo resultado para mesma intencao.
- Idempotency conflict ocorre para mesma chave com digest divergente.
- Reexecucao com outro `reference_time` ou `knowledge_cutoff` e nova query semantica.
- Differencing usa historico auditado de queries relacionadas.
- RLS/tenant isolation impedem leitura direta de outra Organization.

## Verificação e observabilidade

Testes obrigatorios no BUILD:

- unit: disclosure decision, privacy profile, snapshot linkage, idempotency digest;
- application: gate order, release, generalize, suppress, deny;
- integration: migration/RLS/audit append-only;
- API: response uniformity, no IDs, permission, revoked grant, purpose mismatch;
- API behavior: same HTTP behavior, response schema, cache policy, pagination behavior and retry semantics for protected non-release cases;
- latency: no materially distinguishable latency class enabling reliable inference;
- temporal T0/T1/T2: later knowledge nao contamina query anterior;
- differencing: query relacionada que passaria isolada deve ser suprimida/negada quando combinada ao historico;
- validation script em `apps/validacao`.

Observabilidade:

- correlation_id;
- audit_id;
- disclosure decision state interno;
- result_digest;
- sem logs de payload sensivel.

## Documentação afetada

- `docs/adr/0071-market-supply-production-gates-before-cross-tenant-aggregate-api.md`
- `docs/specs/approved/2026-08-28-market-supply-production-gate-closure.md`
- `docs/plans/CUT_F3_MARKET_SUPPLY_AGGREGATE_VISIBILITY_BUILD_PLAN.md`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Riscos, alternativas e perguntas abertas

Riscos:

- resolver produtivo exigir modelo de opt-in ainda inexistente;
- valores de privacy profile serem insuficientes sem dados reais de distribuição;
- timing/cache/status HTTP revelarem motivo de `NOT_RELEASED`;
- audit log armazenar material sensivel demais;
- F3 crescer para CommercialDemand persistido ou report persistido prematuramente.

Alternativa A: implementar apenas API com dados sintenticos. Rejeitada para F3 porque F0 ja cobre mock; F3 deve provar fronteira real.

Alternativa B: persistir CommercialDemand agora. Deferida; adiciona lifecycle comercial antes do primeiro aggregate.

Alternativa C: endpoint producer-side apenas. Ja coberto por F1; nao prova cross-Organization aggregate.

HUMAN REVIEW antes de BUILD:

- confirmar fonte de opt-in/grants para population resolver;
- confirmar valores iniciais de privacy profile ou aceitar profile de teste nao produtivo;
- confirmar schema de audit persistence;
- confirmar contrato HTTP/status/cache/timing;
- confirmar permission/capability name para endpoint.
