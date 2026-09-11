# Commercial Passport Implementation Plan

**Data:** 2026-09-11
**Status:** Plano proposto; F1-F7 ainda nao implementados.

## Objetivo

Implementar Commercial Passport em Titan Livestock como primeiro consumidor real da arquitetura Trust Core, reutilizando Policy, Evaluation, Decision, MarketEligibility, MarketReadiness, MarketOptionality, Dossier, VerificationBundle, AuthorizationGrant e Market Supply quando aplicavel.

## Sequencia aprovada

### F1 — application/domain contracts

Criar contratos Livestock para representar:

- CommercialOpportunity;
- CommercialPassport projection;
- Property readiness section;
- Population eligibility section;
- RequirementAssessment;
- Reasons, gaps e limitations.

Nao persistir ainda.

Nao criar endpoint ainda.

Nao criar Core abstraction.

### F2 — requirement reasoning semantics

Implementar a semantica antes do Passport completo:

- `SATISFIED`;
- `MISSING`;
- `UNKNOWN`;
- `FAILED`;
- `NOT_APPLICABLE`;
- `BLOCKED`.

Regras:

- `MISSING != UNKNOWN`;
- `FAILED != MISSING`;
- `BLOCKED != FAILED`;
- `NOT_APPLICABLE` nao reduz readiness;
- Unknown nao e false;
- Missing nao e non-compliance.

Testes unitarios devem cobrir cada estado e agregacao derivada.

### F3 — Property Commercial Passport

Construir Passport de propriedade como projection dinamica.

Entrada:

- Organization;
- property;
- CommercialOpportunity/MarketProfile;
- temporal context (`reference_time`, `knowledge_cutoff`);
- decisions/evaluations existentes quando aplicavel;
- lacunas e limitacoes.

Saida:

- opportunity;
- property readiness;
- requirement assessments;
- readiness counts;
- blocking requirements;
- reasons/gaps/limitations;
- policy/version;
- reference_time;
- knowledge_cutoff;
- evaluated_at.

### F4 — animal/lot/population eligibility summary

Adicionar summary separado para animal/lot/population.

Nao misturar com property readiness.

Exemplo de dimensoes:

- ready/eligible;
- conditioned;
- not ready;
- unknown;
- not evaluated;
- blocked;
- reassessment required.

Reutilizar `MarketReadinessReport`, `MarketOptionAssessment` e CandidatePopulation quando aplicavel.

### F5 — formal issuance via Dossier/VerificationBundle

Criar fluxo formal somente quando houver emissao/compartilhamento.

Reutilizar:

- Dossier com `VerticalSection`;
- VerificationBundle existente;
- hashes canonicos;
- authorization/audit quando externo.

Nao emitir Dossier/VerificationBundle em cada GET dinamico.

### F6 — API

Projetar API apos F1-F5 estarem validados.

Possiveis rotas, nao obrigatorias:

- `GET /v1/livestock/properties/{id}/commercial-passport`;
- `GET /v1/livestock/properties/{id}/commercial-passport/{opportunity}`;
- `POST /v1/livestock/properties/{id}/commercial-passport/evaluate`;
- `POST /v1/livestock/properties/{id}/commercial-passport/issue`.

Rotas devem seguir convencoes existentes e exigir OrganizationContext/autorizacao.

### F7 — UI projection

Construir UI depois do backend/application.

Objetivos da UI:

- onde posso vender;
- onde quase consigo vender;
- por que nao consigo;
- o que preciso fazer;
- quantos animais estao aptos;
- quando bloqueios temporarios cessam, se derivavel.

UI nao implementa regra de negocio, autorizacao ou score.

## Domain

Commercial Passport pertence a Livestock.

Novos conceitos Core so podem ser propostos se:

1. forem independentes da vertical;
2. tiverem semantica estavel;
3. tiverem ou forem ter mais de um consumidor real;
4. nao dependerem de regras pecuarias;
5. reduzirem duplicacao significativa;
6. preservarem direction of dependency.

## Application

A application layer deve compor:

- MarketEligibilityService;
- MarketReadinessService;
- MarketOptionality quando util;
- FactSnapshot temporal;
- Decisions/Evaluations existentes;
- DossierService somente para issuance formal.

## Infrastructure

F1-F4 devem preferir transience/application-only sempre que possivel.

Persistencia so entra quando houver necessidade atual:

- issuance formal;
- audit duravel;
- idempotency de operacao externa;
- snapshot emitido.

## API e authorization

Consulta dinamica do produtor e operacao interna sob a propria Organization.

Disclosure externo exige AuthorizationGrant/FieldScope/Purpose e audit.

Nenhuma rota deve permitir lookup global de propriedades, animais, lotes ou populacoes.

## Temporal semantics

Todo Passport deve preservar:

- `reference_time`;
- `knowledge_cutoff`;
- `evaluated_at`;
- policy id/version;
- limitations;
- source/evaluation/decision references.

Nao usar somente estado atual do banco para explicar decisao historica.

## Testing

F2 deve cobrir:

1. requisito satisfeito;
2. requisito ausente;
3. requisito desconhecido;
4. requisito falhou;
5. requisito nao aplicavel;
6. blocker;
7. blocker prevalecendo sobre score alto;
8. `NOT_APPLICABLE` fora do denominador;
9. readiness deterministica.

F3-F5 devem cobrir:

- policy version change;
- reference_time diferente;
- knowledge_cutoff diferente;
- evidence arriving later;
- property ready but animals not eligible;
- animals valid but property incomplete;
- snapshot immutability;
- audit envelope;
- tenant isolation;
- authorization;
- deterministic evaluation;
- old issued passport reproducible after new data arrives.

## Validacao manual

Qualquer passo que acrescente comportamento observavel pela API deve criar roteiro em `apps/validacao`, obedecendo as regras do projeto.

## Fora de escopo

- Finance;
- Insurance;
- marketplace;
- buyer-producer matching;
- score financeiro;
- public disclosure;
- blockchain;
- novo Trust subsystem;
- nova Policy engine;
- novo Dossier/Verification framework;
- UI antes do backend/application.
