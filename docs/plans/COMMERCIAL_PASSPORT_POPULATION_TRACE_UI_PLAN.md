# Commercial Passport — Population Trace UI Plan

**Data:** 2026-09-21  
**Status:** IMPLEMENTADO

## Retomada

Objetivo: tornar visíveis na tela do Commercial Passport os metadados agregados que validam a origem
temporal da população, sem expor IDs individuais de animais e sem criar regra de negócio no navegador.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- a projection HTTP do Commercial Passport já expõe `population_snapshot_digest`,
  `selection_criteria_digest`, `commercial_window` e `source_report_reference`;
- a tela `apps/web/src/pages/CommercialPassport.tsx` já apresenta readiness, população, lacunas e cofre
  de evidências;
- `ARCHITECTURE.md` preserva o frontend como camada de apresentação, sem autorização ou regra de domínio
  duplicada no navegador.

## Escopo do corte

- exibir, por oportunidade, um bloco recolhível de rastreio da população;
- mostrar total avaliado, fonte do relatório, digest da população, digest dos critérios e janela comercial;
- declarar explicitamente que a visualização é agregada e não expõe IDs individuais;
- cobrir a tela com teste de frontend.

## Fora de escopo

- nova API ou alteração de contrato HTTP;
- nova regra de classificação no frontend;
- exibir IDs individuais de animais;
- autorização visual;
- upload, edição ou correção de dados pela UI;
- decisão regulatória ou garantia comercial.

## Verificação

- teste focado da página `CommercialPassport`;
- lint e build TypeScript/Vite;
- portão completo antes do commit.
