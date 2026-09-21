# Producer Evidence Vault v1 Plan

**Data:** 2026-09-21  
**Status:** BUILD em andamento

## Retomada

Objetivo: iniciar o cofre de evidências do produtor sem criar armazenamento paralelo ao Core Evidence.
O primeiro corte deve dizer quais evidências são esperadas para resolver lacunas comerciais e quais
referências já existem na projeção.

## Discovery

Resultado: **PROCEED**.

Evidência no repositório:

- Core já possui `Evidence`, `ValidityPeriod`, `ConfidenceLevel`, `EvidenceService` e
  `TransactionalEvidenceRepository`;
- Livestock já referencia evidências do Core por `UniversalReference` em tratamentos, saídas,
  transformações, autoridade de requisito e Commercial Passport;
- o `Commercial Passport` já expõe lacunas acionáveis e requirements com `evidence_references`;
- a trilha de continuidade pede que o Titan saiba dizer quais evidências existem, que período cobrem,
  que finalidade atendem e onde há lacuna.

## Escopo do corte

- criar análise application-only `ProducerEvidenceVaultAnalyzer`;
- derivar necessidades de evidência de requirements e lacunas do Commercial Passport;
- preservar IDs de evidências já referenciadas, sem consultar bytes/documentos;
- classificar necessidades como `SATISFIED`, `MISSING`, `UNKNOWN`, `EXPIRED`, `INSUFFICIENT` ou
  `BLOCKING`;
- expor `evidence_vault` na projection HTTP do Commercial Passport;
- atualizar contrato TypeScript e roteiro executável de validação.

## Fora de escopo

- upload de arquivo;
- blob storage, GridFS ou attachment novo;
- nova tabela ou migration;
- validação/admissibilidade de Evidence;
- associação automática de evidência a fatos;
- UI dedicada do cofre;
- decisão regulatória ou garantia comercial.

## Verificação

- testes application do Commercial Passport cobrindo necessidades de evidência;
- testes API release-gated preservados;
- build TypeScript/Vite;
- roteiro `apps/validacao/commercial_passport_api.py` validando `evidence_vault`;
- portão completo antes do commit.
