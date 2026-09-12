# Commercial Passport Implementation Plan

**Data:** 2026-09-11
**Status:** Plano aprovado; F1-F9 implementados. Proximos cortes: emissao formal produtiva, roteiro executavel e habilitacao controlada da feature flag.

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

### F8 — boundary de pipeline dinamica

Conectar a rota release-gated de consulta dinamica a uma porta de aplicacao.

Regras:

- sem pipeline produtiva injetada, a rota continua fail-closed;
- com pipeline injetada, a rota retorna somente projection derivada;
- o payload HTTP deve ser serializacao canonica do `CommercialPassport`;
- nao criar dados sinteticos;
- nao emitir Dossier/VerificationBundle no GET dinamico;
- nao habilitar feature flag por padrao.

### F9 — pipeline produtiva inicial

Implementar a primeira pipeline produtiva de requisitos de propriedade.

Status: implementado em 12/09/2026 como pipeline inicial baseada em `MarketReadinessReport` canonico.

Objetivo:

- resolver um conjunto inicial de oportunidades/requisitos a partir de fontes existentes;
- reutilizar Policy/Evaluation/Decision/MarketReadiness quando aplicavel;
- preservar `reference_time` e `knowledge_cutoff`;
- produzir reasons/gaps/limitations explicaveis;
- manter `PROPERTY_READINESS` separada de `POPULATION_ELIGIBILITY`.

Nao implementar marketplace, buyer matching, public disclosure ou outro policy engine.

### F10 — emissao formal produtiva

Conectar a rota release-gated de emissao ao material canonico real.

Fluxo esperado:

- projection dinamica produtiva;
- congelamento formal somente quando solicitado;
- `DossierService`;
- `VerificationBundleService`;
- audit/autorizacao quando houver compartilhamento externo.

Regras:

- nao emitir Dossier/VerificationBundle em cada consulta dinamica;
- nao criar segundo framework de snapshot;
- nao persistir disclosure externo sem grant apropriado;
- manter emissao formal diferente de readiness dinamica.

### F11 — roteiro executavel em `apps/validacao`

Criar roteiro manual executavel quando houver fluxo testavel.

O roteiro deve:

- descobrir Organization e entidades necessarias sem copia manual de IDs;
- mostrar requisicao e resposta de cada passo;
- explicar por que cada passo existe;
- sondar ambiente/autenticacao/permissao antes do primeiro passo;
- cobrir consulta dinamica, emissao formal e comportamento fail-closed quando aplicavel.

### F12 — habilitacao controlada da feature flag

Somente apos pipeline produtiva, emissao formal e validacao manual.

`TITAN_COMMERCIAL_PASSPORT_API_ENABLED` permanece desligada por padrao ate la.

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
