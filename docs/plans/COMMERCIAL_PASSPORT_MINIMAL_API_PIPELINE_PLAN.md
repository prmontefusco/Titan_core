# Commercial Passport — Minimal API Pipeline Plan

**Data:** 2026-09-18  
**Status:** BUILD em andamento

## Retomada

Objetivo: conectar a rota release-gated de consulta dinâmica do Commercial Passport a uma projection mínima real, sem parceiro, marketplace, disclosure externo ou emissão formal automática.

Estado atual: os contratos de Commercial Passport, a pipeline `PropertyCommercialPassportMarketReadinessPipeline`, a emissão formal via Dossier/VerificationBundle e a superfície HTTP release-gated já existem. A API ainda retorna 503 por padrão porque nenhuma pipeline é composta no app.

Decisão já aprovada: a trilha de continuidade registrada em `docs/plans/TITAN_CONTINUITY_TRACK_2026-09-16.md` coloca “Commercial Passport pipeline mínima” como próximo incremento após BuyerPolicy.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- `packages/livestock_application/commercial_passport.py` já possui a pipeline produtiva inicial baseada em `MarketReadinessReport`;
- `apps/api/livestock_commercial_passport.py` já possui a rota release-gated e porta de composição;
- `docs/livestock/COMMERCIAL_PASSPORT_IMPLEMENTATION_PLAN.md` proíbe dados sintéticos, disclosure externo, marketplace e novo policy engine.

## Escopo do corte

Implementar somente um composer mínimo e explícito para o GET dinâmico:

- permanece atrás de `TITAN_COMMERCIAL_PASSPORT_API_ENABLED=true`;
- exige também `TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED=true`;
- exige metadados explícitos de uma oportunidade comercial;
- retorna projection dinâmica com lacuna declarada de `MarketReadinessReport` quando ainda não houver relatório canônico;
- mantém emissão formal fail-closed.

## Fora de escopo

- criar mercado real por default;
- avaliar Policy/Rule;
- criar Evaluation ou Decision;
- resolver população de animais;
- emitir Dossier/VerificationBundle no GET;
- habilitar a feature flag por padrão;
- compartilhar dados com comprador ou terceiro.

## Verificação

- teste API para default 503 preservado;
- teste API para pipeline mínima opt-in retornando projection com lacuna explícita;
- roteiro `apps/validacao/commercial_passport_api.py` atualizado para validar 503 ou 200 conforme configuração;
- portão completo do projeto antes do commit.
