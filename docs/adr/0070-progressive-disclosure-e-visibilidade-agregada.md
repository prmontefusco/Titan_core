# ADR-0070 - Progressive disclosure e visibilidade agregada

**Data:** 2026-08-28  
**Estado:** ACCEPTED  
**Escopo:** Core authorization + Titan Livestock

## Contexto

Compradores podem precisar de visao agregada de capacidade. Produtores precisam preservar privacidade, isolamento por Organization e controle de disclosure. `DOMAIN.md` ja define `SharingRequest`, `GrantAssessment`, `AuthorizationGrant`, `AccessPurpose`, `GrantScope`, `GrantScopeResolution`, `FieldScope`, `AccessRestriction`, `DataAccessRecord`, revogacao prospectiva e resposta uniforme para dados inexistentes/invisiveis.

ADR-0065/0068 proibe estender BuyerPolicy para acesso indireto aos fatos do fornecedor. Esta ADR preserva essa fronteira.

## Problema

Visibilidade agregada entre Organizations pode revelar existencia, volume, propriedade, identificadores, gaps sanitarios ou inferencias comerciais se for implementada como consulta cross-tenant comum, redaction superficial ou extensao indevida de Policy sharing.

## Decisao

Progressive disclosure para Market Supply Intelligence deve seguir o principio:

> Aggregate-first, identity-last.

Organization permanece o boundary padrao de tenant/isolation.

Nenhuma relacao concede acesso por si so. Os seguintes fatos nao implicam autorizacao:

- relacao comercial;
- Policy compartilhada;
- identificador conhecido;
- contrato buyer/supplier;
- existencia de `CommercialDemand`;
- participacao na mesma supply network.

Ausencia de grant valido nega acesso.

## Purposes iniciais

Nao usar um purpose amplo generico como `MARKET_SUPPLY`.

Os purposes iniciais aceitos para design futuro sao:

### MARKET_SUPPLY_AGGREGATE_ASSESSMENT

Autoriza somente a superficie analitica agregada aprovada.

Nao autoriza automaticamente identidade de produtor, identidade de propriedade, `AnimalIdentifier`, tratamento individual, Evidence, Dossier, VerificationBundle ou detalhes individuais de Evaluation/Decision.

### MARKET_SUPPLY_CANDIDATE_DISCLOSURE

Aplica-se somente apos contexto comercial/candidate-selection explicito.

Autoriza apenas os campos detalhados permitidos por `FieldScope`/`GrantScope`.

Permissao de aggregate assessment nunca escala silenciosamente para candidate disclosure.

## Participacao de produtores

Participacao de produtor em visibilidade cross-Organization de Market Supply Intelligence e opt-in explicito por padrao.

Um comprador nao pode consultar dados de rebanho de fornecedor apenas porque criou uma `CommercialDemand`.

O primeiro design comercial deve preferir autorizacao limitada por contexto, como comprador, purpose, `CommercialDemand` ou contexto comercial definido, Policy/versao, `GrantScope`, `FieldScope`, `valid_from` e `valid_until`.

Grants longos ou network-level podem ser avaliados no futuro somente com evidencia de necessidade.

## Reuso de Core Authorization

Implementacao futura deve preferir composicao dos conceitos Core existentes:

- `SharingRequest`;
- `GrantAssessment`;
- `AuthorizationGrant`;
- `AccessPurpose`;
- `GrantScope`;
- `GrantScopeResolution`;
- `FieldScope`;
- `AccessRestriction`;
- `DataAccessRecord`.

Nao criar consent model Livestock separado sem documentar insuficiencia concreta dos conceitos Core.

## AggregationPrivacyPolicy

Fica aceito o conceito arquitetural `AggregationPrivacyPolicy` ou nome equivalente alinhado a linguagem do dominio.

Ele nao deve hard-codear um threshold global arbitrario. O design deve suportar:

- pisos minimos configuraveis por deployment, produto ou perfil, como minimo de Organizations, propriedades e sujeitos;
- assessment dinamico de risco considerando contagem de Organizations, propriedades e sujeitos, precisao geografica, atributos raros, combinacao de filtros, janela comercial, raridade de categoria/raca, consultas anteriores relacionadas, risco de differencing, proximidade temporal e consultas repetidas.

Field redaction isolada nao e controle suficiente.

## Reidentificacao e differencing

Protecao contra consultas repetidas e differencing e requisito antes da primeira API agregada cross-Organization de producao.

O design futuro deve permitir registrar/avaliar requester, buyer Organization, `AccessPurpose`, contexto do grant, fingerprint da query, criterios populacionais, filtros, tempo, classificacao do resultado e consultas anteriores relacionadas.

Controles possiveis incluem auditoria, rate limiting, similaridade de queries, deteccao de differencing, suppression/generalization, freshness bands, reducao de precisao geografica, minimos de cohort e negacao temporaria de queries arriscadas.

## Comportamento externo uniforme

Resposta externa nao deve revelar se dado protegido nao existe, existe mas esta invisivel, foi excluido por autorizacao ou pertence a outra Organization.

Nao vazar existencia por status HTTP, contagens, metadados, timing, paginacao ou mensagens de erro.

## Revogacao

Revogacao e prospectiva.

Apos revogacao efetiva:

```text
new query -> DENIED
query reexecution -> DENIED
new analytical report -> DENIED
new detailed disclosure -> DENIED
```

Material previamente entregue legitimamente nao e apagado da historia, permanece auditavel e nao prova autorizacao atual. O sistema deve distinguir validade da autorizacao, existencia historica do artefato, usabilidade atual do artefato e direitos de redistribuicao.

Relatorios antigos precisam carregar metadados temporais e de autorizacao suficientes para nao serem apresentados como analise corrente.

## Exportacao e redistribuicao

Decisao inicial: `DENY BY DEFAULT`.

Visualizar analytics agregada dentro do Titan nao autoriza CSV, PDF, API extraction, redistribuicao, ingestao em IA externa, analytics secundaria, revenda ou publicacao.

Exportacao ou redistribuicao futura exige autorizacao explicita por `AccessPurpose` e/ou operacao especifica, `GrantScope`, `FieldScope` e restricoes aplicaveis.

## Auditoria

Acesso cross-Organization de Market Supply deve ser auditavel.

Implementacao futura deve reutilizar audit concepts existentes e preservar, conforme aplicavel, solicitante, buyer Organization, purpose, grant usado, scope, fields pedidos, contexto da query/populacao, instante, resultado allow/deny, artefato gerado e estado de revogacao.

Nao criar subsistema de auditoria Livestock independente.

## Fluxo preservado

```text
CommercialDemand
        |
        v
CandidatePopulationCriteria
        |
        v
PopulationResolver
        |
        v
CandidatePopulationSnapshot / resolved context
        |
        +--> MarketReadiness
        |
        +--> GapAnalysis
        |
        +--> optional SupplyForecast
                    |
                    v
            SupplyDemandAnalysis
                    |
                    v
            SupplyIntelligenceReport
```

Autorizacao circunda population resolution e disclosure. Ela nao e filtro posterior.

## Alternativas

1. Compor conceitos Core de Authorization, Purpose, GrantScope, FieldScope e Audit.
2. Criar consent model Livestock separado.
3. Permitir aggregate API ampla para compradores.

## Justificativa

A alternativa 1 preserva `DOMAIN.md` P-172, P-179, P-180, P-196, P-198 e P-200. A alternativa 2 duplicaria modelo Core sem insuficiencia demonstrada. A alternativa 3 violaria isolamento, privacidade e resposta uniforme.

## Consequencias

- CUT F nao pode implementar API agregada cross-Organization antes dos controles de autorizacao, auditoria e aggregation privacy.
- `MARKET_SUPPLY_AGGREGATE_ASSESSMENT` e `MARKET_SUPPLY_CANDIDATE_DISCLOSURE` devem permanecer separados.
- Producer participation e opt-in explicito por padrao.
- Revogacao bloqueia novos acessos, mas nao reescreve historia.
- Exportacao/redistribuicao e negada por padrao.
- Esta ADR nao altera a semantica de Dossier, VerificationBundle, Evidence, Evaluation ou Decision.

## Decisoes resolvidas nesta ADR

- `Aggregate-first, identity-last`.
- Ausencia de grant nega acesso.
- Dois purposes iniciais separados.
- Participacao de produtor opt-in por padrao.
- Reusar Core Authorization antes de novo consent model.
- Aceitar conceito de `AggregationPrivacyPolicy` ou equivalente.
- Exigir controles contra reidentificacao/differencing antes de API agregada cross-Organization.
- Resposta externa uniforme para inexistente/invisivel/excluido.
- Revogacao prospectiva.
- Exportacao/redistribuicao deny-by-default.
- Auditoria obrigatoria para acesso cross-Organization de Market Supply.

## Decisoes futuras

- Especificar contrato de implementacao para cada AccessPurpose.
- Definir perfis concretos de `GrantScope` e `FieldScope`.
- Definir formato tecnico de `AggregationPrivacyPolicy`.
- Definir thresholds/configuracoes por perfil sem regra global arbitraria.
- Definir audit tier e volume/custo antes de producao.
- Definir UX/fluxo operacional de opt-in e revogacao.

Esta ADR aceita a arquitetura de progressive disclosure, mas nao autoriza codigo, migration, API, worker, endpoint cross-tenant, grant persistence novo ou CUT F.
