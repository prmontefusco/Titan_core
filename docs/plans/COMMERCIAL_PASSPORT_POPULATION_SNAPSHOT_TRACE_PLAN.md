# Commercial Passport — Population Snapshot Trace Plan

**Data:** 2026-09-21  
**Status:** IMPLEMENTADO

## Retomada

Objetivo: tornar a população exibida pelo Commercial Passport mais auditável e temporalmente rastreável,
sem consultar novos eventos, sem criar persistência e sem transformar a projeção em decisão regulatória.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `CandidatePopulationSnapshot` já preserva digest do snapshot, digest dos critérios e janela comercial;
- `MarketSupplyReadinessCompositionService` já constrói `MarketReadinessReport` a partir de snapshots
  autorizados;
- `Commercial Passport` já consome `MarketReadinessReport` e expõe resumo populacional por status;
- `ARCHITECTURE.md` preserva Presentation como exibição de estado autorizado, sem decisão jurídica ou de
  negócio.

## Escopo do corte

- adicionar metadados opcionais de snapshot populacional ao `MarketReadinessReport`;
- propagar digest da população, digest dos critérios e janela comercial quando o relatório vem de
  `CandidatePopulationSnapshot`;
- expor esses metadados no `PopulationEligibilitySummary` e na projection HTTP do Commercial Passport;
- atualizar contrato TypeScript e roteiro executável de validação;
- cobrir a propagação com testes application/API/frontend.

## Fora de escopo

- resolver animais por movimento/saída em nova query;
- alterar RLS, grants ou autorização;
- criar tabela, migration ou persistência de snapshot;
- expor IDs individuais de animais;
- criar nova API;
- alterar política de elegibilidade, MarketReadiness ou classificação de lacunas;
- decisão regulatória, garantia comercial ou autorização visual.

## Verificação

- testes application de Commercial Passport e Market Supply;
- testes API release-gated de Commercial Passport;
- testes de fumaça do roteiro `apps/validacao`;
- teste e build do frontend;
- portão completo antes do commit.
