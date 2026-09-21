# Commercial Passport — Gap Engine v1 Plan

**Data:** 2026-09-18  
**Status:** BUILD em andamento

## Retomada

Objetivo: transformar o Commercial Passport de uma projeção estática de readiness em uma orientação
operacional mínima, mostrando lacunas acionáveis e próxima ação possível por oportunidade.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `CommercialPassportRequirementStatus` já distingue `MISSING`, `UNKNOWN`, `FAILED` e `BLOCKED`;
- `PopulationEligibilitySummary` já traz contagens agregadas por `MarketReadinessStatus`;
- `docs/plans/TITAN_CONTINUITY_TRACK_2026-09-16.md` prioriza classificar lacunas como `MISSING`,
  `UNKNOWN`, `EXPIRED`, `INSUFFICIENT` ou `BLOCKING`, preservando que recomendação não é decisão
  regulatória, garantia comercial nem substituto de Policy/Evaluation/Decision;
- `docs/plans/MARKET_SUPPLY_INTELLIGENCE_DESIGN_PACKAGE.md` rejeita um gap engine separado para Market
  Supply, então este corte fica restrito ao Commercial Passport e deriva somente de material já presente
  na projeção.

## Escopo do corte

- criar análise operacional agregada para Commercial Passport;
- classificar lacunas de propriedade e população;
- gerar uma ação recomendada simples e determinística;
- expor `gap_analysis` na projeção HTTP já release-gated;
- atualizar tipos do frontend e roteiro executável de validação.

## Fora de escopo

- nova Policy/Rule/Evaluation/Decision;
- persistência, migration, snapshot formal ou emissão automática;
- taxonomia comercial paralela;
- exposição de identificadores individuais da população;
- marketplace, matching de compradores ou garantia de aceite comercial;
- UI nova.

## Verificação

- testes application do Commercial Passport cobrindo classificação e serialização;
- testes API release-gated preservados;
- roteiro `apps/validacao/commercial_passport_api.py` validando `gap_analysis`;
- portão completo antes do commit.
