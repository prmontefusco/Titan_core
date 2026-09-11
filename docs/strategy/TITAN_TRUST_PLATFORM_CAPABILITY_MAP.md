# Titan Trust Platform Capability Map

**Data:** 2026-09-11
**Status:** Strategic capability map
**Objetivo:** preservar oportunidades estrategicas sem transforma-las em backlog imediato.

## Principio

TITAN = infraestrutura de confianca para negocios agropecuarios e cadeias reguladas.

O Titan deve registrar fatos e evidencias preferencialmente uma unica vez. Diferentes produtos podem derivar avaliacoes, decisoes, dossies ou disclosures distintos, desde que preservem provenance, temporalidade, autorizacao, escopo e limitacoes.

Este mapa nao autoriza implementacao alem do escopo aprovado.

## NOW

### Trust Core evolution

Reconhecer e documentar que o Core existente ja fornece as primitivas de confianca:

- FactSnapshot;
- Evidence;
- Policy;
- Rule;
- Evaluation;
- Decision;
- Dossier;
- VerificationBundle;
- AuthorizationGrant;
- audit, integrity, idempotency, events, outbox/inbox;
- Organization boundaries.

Restricao: Trust Core nao e novo modulo, novo servico, nova engine ou subsistema paralelo.

### Commercial Passport

Implementar, em Titan Livestock, o primeiro produto concreto baseado nessa arquitetura.

Commercial Passport e uma projection/application view que compoe oportunidades comerciais, property readiness, population eligibility, reasons, gaps e limitations a partir de avaliacoes e decisoes existentes.

Restricoes:

- CommercialPassport != Decision;
- CommercialPassport != MarketEligibility;
- CommercialPassport nao e fonte de verdade;
- nenhuma emissao formal automatica em consulta dinamica;
- sem disclosure cross-tenant sem autorizacao.

## NEXT

### Market Supply integration

Integrar Commercial Passport com Market Supply apenas atraves do pipeline ja aprovado:

```text
authorization
-> population
-> disclosure
-> aggregate
-> audit
```

Preservar progressive disclosure, identity-last e minimizacao. Unknown, inaccessible, excluded e not evaluated devem permanecer explicitos internamente.

### External commercial disclosure

Permitir compartilhamento comercial externo somente com AuthorizationGrant, FieldScope, finalidade, audit, limitacoes e controle de privacidade. Disclosure nao e permissao implicita para contato direto, redistribuicao, inferencia ou enriquecimento.

### Certification profiles

Perfis de certificacao podem reutilizar os mesmos fatos/evidencias e emitir avaliacoes ou dossies diferentes. Certificacoes permanecem em Livestock enquanto dependerem de requisitos agropecuarios concretos.

## LATER

### Agricultural Trust Profile / Finance Dossier

Produtor pode autorizar compartilhamento de evidencias agregadas com banco, cooperativa ou fintech.

Invariantes:

- jamais criar score financeiro opaco;
- fornecer evidencias, indicadores, provenance e limitacoes;
- separar material factual de conclusao financeira de terceiros;
- disclosure somente por grant e purpose.

### Insurance Dossier

Seguradoras podem consumir evidencias verificaveis de historico produtivo, sanitario, ambiental e operacional.

Nao implementar agora. Nao criar produto de underwriting, precificacao ou decisao securitaria dentro do Titan sem discovery propria.

### Sustainability and certifications

Multiplas certificacoes podem derivar da mesma base de evidencias. As regras podem divergir, mas nao devem duplicar fatos como fonte de verdade paralela.

### Property Operations / Property OS

Custos, estoque, tarefas, producao e indicadores podem ser produtos futuros somente quando fizer sentido reutilizar fatos existentes.

Nao transformar Titan em ERP. Operacoes de propriedade nao devem enfraquecer auditabilidade, provenance ou isolamento por Organization.

### Technician / Cooperative / Association operating model

Tecnicos, cooperativas e associacoes podem auxiliar produtores, especialmente quando ha baixa maturidade digital.

Esse modelo exige autorizacao granular, capacity binding, field scope, audit e possibilidade de revogacao. Nao deve criar acesso automatico por relacionamento institucional.

## Fora de escopo atual

- finance product;
- insurance product;
- marketplace;
- buyer-producer matching;
- opaque scores;
- public producer search;
- blockchain;
- new Trust subsystem;
- new policy engine;
- new dossier or verification framework;
- Core-specific concepts for Livestock commercial constraints.
