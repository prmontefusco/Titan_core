# ADR-0081 — Trust Core como infraestrutura existente de evidencia para decisao

**Data:** 2026-09-11
**Status:** PROPOSTA
**Escopo:** consolidacao arquitetural. Nao autoriza implementacao F1-F7 do Commercial Passport.

## Contexto

O Titan evolui conceitualmente de rastreabilidade e compliance pecuario para uma infraestrutura de confianca para negocios agropecuarios e cadeias reguladas.

O Core ja contem primitives de confianca suficientes para esse direcionamento: `FactSnapshot`, `Evidence`, `Policy`, `Rule`, `Evaluation`, `Decision`, `Dossier`, `VerificationBundle`, authorization, audit, integrity, idempotency, events, outbox/inbox e isolamento por Organization.

A necessidade atual e reconhecer, documentar e endurecer essa infraestrutura, nao criar uma engine paralela.

## Problema

Sem uma decisao explicita, existe risco de:

- criar `trust_engine`, `trust_service` ou outro subsistema paralelo;
- duplicar Evaluation/Decision/Dossier/VerificationBundle;
- promover conceitos Livestock ao Core;
- transformar projections em fontes de verdade;
- enfraquecer temporalidade, provenance, audit e authorization.

## Decisao

O Trust Core e o Core existente reconhecido como infraestrutura reutilizavel de evidencia para avaliacao, decisao, verificacao e disclosure autorizado.

Trust Core nao e um novo modulo.

Nao deve existir novo `trust_engine`, `trust_service`, pacote `trust_*` ou subsistema paralelo.

**No separate Trust subsystem shall be created.**

`FactSnapshot`, `Evidence`, `Policy`, `Rule`, `Evaluation`, `Decision`, `Dossier`, `VerificationBundle`, audit, integrity, authorization, events, idempotency, outbox/inbox e Organization boundaries formam a infraestrutura existente.

Verticais fornecem semantica de dominio.

Core fornece primitivas genericas.

O fluxo arquitetural preservado e:

```text
vertical facts / evidence
-> core trust primitives
-> evaluations / decisions
-> dossiers / verification bundles
-> authorized disclosure / vertical products
```

## Consequencias

### Positivas

- Evita duplicacao de mecanismos centrais.
- Preserva direcao de dependencia: Core nao conhece vertical.
- Permite que Livestock, Asset e futuras verticais reutilizem a mesma cadeia de confianca.
- Mantem Decisions historicas reproduziveis.
- Reforca que projections e dashboards nao sao fonte de verdade.

### Negativas

- Produtos verticais precisam compor primitivas existentes em vez de ganhar shortcuts.
- Algumas lacunas de dominio ficam em Livestock ate existir segundo consumidor real.
- Exige disciplina documental para nao tratar capability map como backlog automatico.

## Invariantes

- Core nao conhece bovino, animal, GTA, frigorifico, SISBOV, mercado pecuario, medicamento veterinario ou propriedade pecuaria.
- Verticais nao criam mecanismo paralelo para Policy/Evaluation/Decision/Dossier/VerificationBundle.
- Uma Decision nunca e Fact.
- Uma Evaluation nunca reescreve FactSnapshot historico.
- Um fato posterior nao altera silenciosamente Decision historica.
- `reference_time` e `knowledge_cutoff` sao dimensoes separadas.
- Unknown nao e false.
- Missing evidence nao e non-compliance.
- Projection nao e source of truth.
- Disclosure cross-tenant exige autorizacao, escopo, finalidade e audit.

## Comercial Passport como primeiro consumidor

Commercial Passport pertence a Livestock.

CommercialPassport != Decision.

CommercialPassport != MarketEligibility.

Commercial Passport e uma projection/application view composta por multiplas avaliacoes e decisoes existentes:

```text
CommercialOpportunity
-> Property readiness
-> Population eligibility
-> Reasons / gaps / limitations
```

O Core nao ganha conceito de CommercialPassport. Quando houver emissao formal, Livestock deve reutilizar Dossier e VerificationBundle existentes com secao vertical adequada.

## Alternativas consideradas

### Criar um Trust Engine

Rejeitada. Duplicaria Evaluation/Decision e criaria um novo centro de autoridade sem necessidade.

### Criar um pacote `trust_core`

Rejeitada. A infraestrutura ja existe em `core_domain`, `core_application`, `core_infrastructure`, `core_integrity` e `shared_kernel`.

### Promover Commercial Passport ao Core

Rejeitada. Passport e produto vertical de Livestock e depende de semantica comercial agropecuaria.

### Usar apenas docs sem ADR

Rejeitada. O risco de arquitetura paralela e suficientemente relevante para exigir decisao arquitetural explicita.

## Relacao com ADRs existentes

Esta ADR consolida e referencia ADR-0010, 0015, 0016, 0018, 0019, 0041, 0044, 0048, 0049, 0051, 0052, 0055, 0060, 0069-0073, 0078 e 0080.

Nao substitui nenhuma delas.

## Criterios de aceitacao

- Documentos de Commercial Passport preservam a separacao Core vs Livestock.
- Nenhum arquivo de producao cria pacote ou servico `trust_*`.
- F1 do Commercial Passport reutiliza conceitos existentes e comeca por contratos e requirement reasoning.
- Dossier/VerificationBundle sao usados somente para emissao formal, nao para consulta dinamica.
