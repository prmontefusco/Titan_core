# Producer Evidence Vault — UI Plan

**Data:** 2026-09-21  
**Status:** IMPLEMENTADO

## Retomada

Objetivo: tornar o `evidence_vault` do Commercial Passport visível na experiência web já existente,
sem criar um produto separado de gestão documental e sem duplicar a autoridade de `Evidence` do Core.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `commercial_passport_projection()` já expõe `evidence_vault` com necessidades, status, referências e
  limitações;
- `apps/web/src/api/commercialPassport.ts` já possui o contrato tipado de `evidence_vault`;
- `apps/web/src/pages/CommercialPassport.tsx` já é a superfície web release-gated onde readiness,
  população e lacunas operacionais são apresentados;
- `ARCHITECTURE.md` preserva a fronteira de Presentation: exibir estado autorizado sem transformar
  resultado técnico em conclusão jurídica, regulatória ou comercial.

## Escopo do corte

- exibir contagem de necessidades de evidência pendentes;
- exibir distribuição por status;
- listar necessidades com oportunidade, tipo de evidência, cobertura esperada, próxima ação e IDs de
  evidências já referenciadas;
- exibir limitações do cofre;
- cobrir a tela com teste de frontend.

## Fora de escopo

- upload de arquivo;
- blob storage, GridFS ou attachment novo;
- nova API;
- nova regra de classificação no frontend;
- validação/admissibilidade de Evidence;
- associação automática de evidência a fatos;
- UI dedicada fora do Commercial Passport;
- decisão regulatória, garantia comercial ou autorização visual.

## Verificação

- teste focado da página `CommercialPassport`;
- suíte frontend completa;
- lint e build TypeScript/Vite;
- portão completo antes do commit.
