# Commercial Passport — Temporal Property Population Plan

**Data:** 2026-09-21  
**Status:** IMPLEMENTADO

## Retomada

Objetivo: fazer a população do Commercial Passport respeitar a permanência temporal do animal na
propriedade no `reference_time`, usando dados persistidos de `property_stays` e preservando o fallback
por propriedade de nascimento apenas quando ainda não houver timeline de estadias.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `MovementService` mantém `PropertyStay` ao registrar movimentações;
- `property_stays` já persiste `start_time`, `end_time`, `status` e `source_movement_id`;
- o adapter `TransactionalPropertyCommercialPassportReadinessPipeline` já compõe a população do
  Commercial Passport a partir do PostgreSQL;
- o corte anterior já tornou a population summary rastreável a snapshot/digests, sem expor IDs
  individuais.

## Escopo do corte

- resolver animais ativos na propriedade por `property_stays` vigente no `reference_time`;
- excluir permanências cujo movimento fonte ainda não era conhecido no `knowledge_cutoff`;
- excluir animais com saída anterior ou igual ao `reference_time`;
- manter fallback por `birth_property_id` somente quando o animal não possui timeline de estadias;
- cobrir o adapter com teste PostgreSQL/RLS focado.

## Fora de escopo

- criar nova tabela ou migration;
- reconstruir timelines antigas automaticamente;
- alterar `MovementService`, regras de movimentação ou saída;
- alterar API pública ou contrato frontend;
- expor IDs individuais na projection HTTP;
- alterar Policy, Evaluation, Decision ou MarketReadiness;
- resolver população cross-Organization ou buyer-facing;
- decisão regulatória, garantia comercial ou autorização visual.

## Verificação

- teste PostgreSQL focado do adapter de Commercial Passport;
- testes API/application de Commercial Passport preservados;
- Ruff, Mypy e portão completo antes do commit.
