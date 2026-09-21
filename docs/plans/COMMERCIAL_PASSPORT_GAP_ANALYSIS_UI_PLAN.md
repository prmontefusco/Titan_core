# Commercial Passport — Gap Analysis UI Plan

**Data:** 2026-09-21  
**Status:** BUILD em andamento

## Retomada

Objetivo: tornar o `gap_analysis` do Commercial Passport visível na experiência web já existente,
sem duplicar regra de negócio no navegador.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `apps/web/src/pages/CommercialPassport.tsx` já apresenta oportunidades, readiness de propriedade e
  resumo populacional;
- `apps/web/src/api/commercialPassport.ts` já possui o contrato tipado de `gap_analysis`;
- `ARCHITECTURE.md` preserva a fronteira de Presentation: exibir estado, lacunas e limitações sem
  transformar resultado técnico em decisão jurídica ou de negócio.

## Escopo do corte

- exibir contagem total de lacunas acionáveis;
- exibir contagens por categoria;
- listar lacunas agregadas com oportunidade, categoria, contagem afetada quando existir e próxima ação;
- exibir limitações da análise;
- cobrir a tela com teste de frontend.

## Fora de escopo

- nova API;
- nova regra de classificação no frontend;
- autorização visual;
- edição/correção de evidências pela UI;
- marketplace, matching de comprador ou garantia comercial;
- snapshot formal ou emissão de Dossier/VerificationBundle.

## Verificação

- teste focado da página `CommercialPassport`;
- build TypeScript/Vite;
- portão completo antes do commit.
