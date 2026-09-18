# Commercial Passport — Property MarketReadiness Report Plan

**Data:** 2026-09-18  
**Status:** BUILD em andamento

## Retomada

Objetivo: substituir a lacuna operacional `MARKET_READINESS_REPORT_MISSING`, quando possível, por um
`MarketReadinessReport` canônico composto a partir de dados persistidos da própria Organization.

Estado atual: a API release-gated já possui pipeline mínima opt-in e oportunidade configurada. O corte
anterior ainda não resolvia população nem `MarketReadinessReport`; retornava gap declarado para preservar
fail-closed sem inventar avaliação.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `MarketReadinessPopulationReader` já compõe readiness a partir de `Decision`/`Evaluation` existentes;
- `animals.birth_property_id` e `animal_exits` permitem resolver uma população operacional simples da
  propriedade sem criar entidade nova;
- `PropertyCommercialPassportMarketReadinessPipeline` já consome `MarketReadinessReport` e serializa o
  resumo populacional separado de `PROPERTY_READINESS`.

## Escopo do corte

- criar adapter de infraestrutura transacional para Commercial Passport;
- listar animais ativos nascidos na propriedade da Organization ativa;
- compor `MarketReadinessReport` usando `Decision`/`Evaluation` existentes;
- retornar `PopulationEligibilitySummary` no GET dinâmico quando a pipeline opt-in estiver configurada;
- manter emissão formal desligada.

## Fora de escopo

- avaliar Policy/Rule;
- criar `Evaluation` ou `Decision`;
- inferir mercado real;
- resolver permanência/movimentação territorial completa;
- usar população por lote;
- disclosure externo;
- Dossier/VerificationBundle no GET;
- migration ou persistência nova.

## Verificação

- testes API para wiring configurado e response com summary populacional;
- testes application Commercial Passport preservados;
- roteiro `apps/validacao/commercial_passport_api.py` atualizado;
- portão completo antes do commit.
