# ADR-0071 - Market Supply production gates before cross-tenant aggregate API

**Data:** 2026-08-28  
**Estado:** ACCEPTED WITH CHANGES  
**Escopo:** Titan Livestock + Core authorization/audit composition

## Contexto

ADR-0069 aceita Market Supply Intelligence como analise nao regulatoria. ADR-0070 aceita progressive disclosure com `aggregate-first, identity-last`. CUT F0-F2H implementaram apenas componentes seguros em memoria e sem API: prototipo sintetico, agregacao producer-side, authorization guard, privacy assessment, audit envelope, resposta publica uniforme, revogacao efetiva, Candidate Population snapshot e binding da snapshot ao workflow.

O proximo risco arquitetural e criar uma API agregada cross-Organization antes de fechar os gates produtivos de privacidade, auditoria, idempotencia, resolver de populacao e comportamento externo.

## Problema

Uma resposta agregada buyer-facing pode revelar dados protegidos por pequenos grupos, filtros, diferencas entre consultas, timing, cache, paginacao, revogacao tardia ou resolucao de populacao ampla demais. Componentes em memoria reduzem risco de design, mas nao bastam para producao sem persistencia/auditoria e perfil operacional.

## Decisao

Nenhuma API agregada cross-tenant de Market Supply pode ser implementada sem os gates abaixo. Esta ADR fica aceita com as condicoes registradas pelo Product Owner:

1. `reference_time` e `knowledge_cutoff` sao invariantes obrigatorias.
2. `AuthorizationDecision` e `DisclosureDecision` permanecem conceitos distintos.
3. `DisclosureDecision` e conceito arquitetural explicito.
4. comportamento publico uniforme protege contra inferencia sem destruir utilidade comercial agregada.
5. Snapshot -> Disclosure -> Result -> Audit e uma invariavel.
6. historico suficiente para semantic differencing e obrigatorio, sem exigir Differential Privacy matematica nesta fase.

Cross-tenant aggregation nao e apenas consulta mais `GROUP BY`; e superficie de disclosure controlado.

Data access, data contribution, derived knowledge e disclosure sao conceitos diferentes. Autorizacao para contribuir dados ao Market Supply nao implica inclusao em todo resultado agregado. A avaliacao de privacidade pode suprimir, generalizar ou excluir contribuicoes autorizadas quando a participacao tornaria o conjunto identificavel.

### 1. Privacy profile versionado

`AggregationPrivacyPolicy` deve ser configuravel e versionado. O codigo pode conter o mecanismo, mas valores produtivos concretos exigem aprovacao. O perfil deve cobrir:

- minimo de Organizations;
- minimo de propriedades;
- minimo de sujeitos;
- precisao geografica maxima;
- atributos raros/sensiveis;
- maximo de filtros combinados;
- repeated-query window;
- differencing/similarity strategy;
- comportamento de suppression/generalization/deny.

Nao existe threshold global universal no dominio.

O perfil deve permanecer aberto a controles de distribuicao, como dominance ratio, concentracao de contribuicao, unicidade geografica, raridade de atributo e raridade temporal, sem exigir que todos sejam implementados no primeiro F3.

### 2. Audit/query persistence

Market Supply precisa de audit/query log proprio ou extensao formalmente aprovada de audit existente. A decisao aceita e criar conceito proprio, inicialmente chamado `MarketSupplyQueryAuditRecord`, porque `shared_policy_access_log` representa acesso a Policy compartilhada e nao analytics agregada.

O log deve preservar material suficiente para auditoria sem expor dados publicamente:

- requester/buyer Organization;
- purpose;
- authorization context digest;
- policy_id/policy_version;
- privacy_profile_id/privacy_profile_version;
- candidate_population_digest;
- query_fingerprint;
- reference_time;
- knowledge_cutoff;
- disclosure_decision;
- decision_reason_codes;
- result_digest, quando houver resultado liberado;
- requested_at;
- evaluated_at;
- revocation_state;
- correlation_id;
- idempotency_reference.

### 3. Candidate Population resolver aprovado

O resolver produtivo nao pode ser lookup global de Animal. Ele deve operar apenas sobre Organizations/fontes autorizadas por opt-in/grant e produzir `CandidatePopulationSnapshot` com digest canonico antes da agregacao. Dados inacessiveis, desconhecidos e excluidos devem permanecer distinguiveis internamente sem vazar membership individual.

O snapshot nao deve registrar apenas o digest final da populacao. Ele deve explicitar o universo logico avaliado, preservando, conforme aprovado no corte produtivo:

- authorized_sources_digest;
- selection_criteria_digest;
- reference_time;
- knowledge_cutoff;
- population_digest;
- population_size;
- organization_count;
- property_count;
- subject_count.

Counts podem permanecer internos quando sua exposicao publica aumentar risco de inferencia.

### 4. Snapshot/digest linkage

O fingerprint de privacy/audit deve apontar para o digest do `CandidatePopulationSnapshot`. Payload agregado, audit envelope e resposta publica nao podem ser produzidos se snapshot, fingerprint, purpose, Policy ou Organization divergirem.

Nenhum aggregate result existe validamente de forma independente de seu `CandidatePopulationSnapshot` e sua `DisclosureDecision`.

```text
AggregateResult
      |
      +-- CandidatePopulationSnapshot
      |
      +-- DisclosureDecision
      |
      +-- MarketSupplyQueryAuditRecord
```

Se snapshot, disclosure decision ou audit record obrigatorio estiver ausente, o resultado nao e valido para disclosure.

### 4B. DisclosureDecision

`DisclosureDecision` e o resultado imutavel da avaliacao de disclosure/privacy para uma query e uma populacao candidata.

Nao e `Evaluation`, nao e `Decision` regulatoria e nao reconhece elegibilidade. Ele responde apenas se um resultado analitico pode ser revelado naquele contexto.

Estados iniciais:

- `ALLOW`;
- `GENERALIZE`;
- `SUPPRESS`;
- `DENY`.

Campos minimos futuros:

- state;
- reason_codes;
- privacy_policy_version;
- query_fingerprint;
- candidate_population_digest;
- evaluated_at;
- evaluator/version, quando aplicavel.

Pode nascer como Value Object ou resultado imutavel do servico de privacy; nao precisa ser Aggregate Root na primeira implementacao.

### 5. Idempotency

Endpoint futuro deve usar idempotencia Core com escopo semantico contendo buyer Organization, purpose, Policy/version, demand/context digest, candidate criteria digest, `reference_time`, `knowledge_cutoff` e idempotency key. Repeticao equivalente retorna resultado canonico; mesma chave com digest divergente gera conflito explicito.

Toda avaliacao de Market Supply deve vincular `reference_time` e `knowledge_cutoff`. Reexecucao com coordenadas temporais diferentes e uma query semanticamente distinta. Isso preserva a diferenca entre "o que era verdadeiro em T" e "o que era conhecido em T".

### 6. Rate limit and semantic differencing

Rate limit de volume pode ser implantacao/gateway. Differencing semantico e responsabilidade da aplicacao porque depende de query fingerprint, filtros, tempo, geografia, atributos raros e historico auditado de consultas relacionadas.

O primeiro F3 nao precisa implementar Differential Privacy matematica formal, mas precisa preservar historico suficiente para avaliar consultas semanticamente relacionadas:

```text
QueryHistory
      |
      v
SemanticSimilarity
      |
      v
DisclosureRisk
```

Repeated-query window isolada nao basta quando consultas diferentes podem ser combinadas para revelar a contribuicao de uma propriedade, Organization ou grupo raro.

### 7. Uniform public behavior

Comportamento externamente observavel nao deve permitir que o requester distinga ausencia de nao-visibilidade, exclusao ou supressao por privacidade quando essa distincao puder revelar membership ou atributos protegidos.

Isso nao exige que todo resultado comercial pareca igual. A API futura pode distinguir utilmente "ha oferta agregada liberada" de "nenhuma informacao pode ser apresentada" quando essa distincao nao revelar dado protegido. Status HTTP, cache, timing, pagination, retry e telemetry precisam de decisao antes de API.

### 8. Revocation

Revogacao efetiva bloqueia novas consultas, reexecucoes e novos relatorios. Artefatos previamente entregues legitimamente permanecem auditaveis e nao provam autorizacao atual. F3 deve registrar o estado de revogacao observado no momento da consulta.

### 9. CommercialDemand first use

Recomendacao: primeiro F3 usa `CommercialDemand` como contexto transitorio de request/validacao, nao como Aggregate Root ou persistencia comercial. Persistir `CommercialDemand` fica para corte posterior se o workflow comercial exigir ciclo de vida.

## Alternativas

1. Implementar F3 imediatamente com os componentes em memoria.
2. Fechar gates produtivos em ADR/SPEC antes de F3.
3. Exigir persistencia completa de CommercialDemand e SupplyIntelligenceReport antes de qualquer API agregada.

## Justificativa

A alternativa 2 e a menor que preserva seguranca, auditoria e incrementalidade. A alternativa 1 cria risco de vazamento e auditoria insuficiente. A alternativa 3 adiciona lifecycle comercial antes de provar o valor e a seguranca da primeira superficie agregada.

## Consequencias

- CUT F3 pode ser especificado apos esta ADR, mas implementacao de endpoint continua condicionada a SPEC/PLAN de F3 com os gates aqui definidos.
- F3 deve entregar primeiro uma superficie agregada minima, nao detalhes.
- `CommercialDemand` persistido, `SupplyForecast`, `SupplyIntelligenceReport` persistido e candidate disclosure detalhado permanecem cortes separados.
- Toda implementacao futura deve incluir testes de tenant isolation, revogacao, idempotencia, differencing, temporalidade e resposta uniforme.
- `DisclosureDecision` passa a ser conceito arquitetural de Market Supply.
- `MarketSupplyQueryAuditRecord` passa a ser o conceito preferido para auditoria de queries Market Supply.
- `DATA ACCESS != DATA CONTRIBUTION != DERIVED KNOWLEDGE != DISCLOSURE` deve ser tratado como principio arquitetural candidato para generalizacao futura no Titan.

## Decisoes humanas necessarias

- Aprovar valores concretos do privacy profile.
- Aprovar modelo de audit/query persistence e retention.
- Aprovar contrato HTTP/timing/cache/pagination.
- Aprovar fontes do resolver produtivo.
- Aprovar plano tecnico de F3 antes de qualquer endpoint.
