# ADR-0059 — Correção de isolamento e temporalidade pós-auditoria

**Status:** ACEITA
**Data:** 13 de agosto de 2026
**Decisor:** responsável pelo produto e arquitetura do Titan

## Contexto

A auditoria independente, executada com banco descartável e semeadura nova, revelou
divergências entre a implementação e invariantes já aceitos: políticas RLS permissivas
para registros append-only, possibilidade de referências entre tenants inconsistentes e
seleção histórica que podia apresentar estado atual ou conhecimento posterior como se
estivessem disponíveis no passado.

Não se cria uma semântica nova. Esta ADR torna executáveis as ADR-0003, ADR-0041,
ADR-0052, ADR-0056 e ADR-0058.

## Decisão

1. Registros declarados append-only recebem políticas RLS explícitas somente para
   `SELECT` e `INSERT`; `UPDATE` e `DELETE` não são autorizados pela policy.
2. Relações tenant-scoped cuja coerência é necessária ao significado do registro devem
   ser protegidas também no banco, por chave composta, constraint equivalente ou
   mecanismo declarativo verificável. A checagem de serviço permanece defesa adicional.
3. A aplicação em execução usa credencial sem `SUPERUSER`, `BYPASSRLS` ou ownership das
   tabelas protegidas. Migrations administrativas usam conexão separada e não servem de
   configuração de runtime.
4. Uma seleção histórica declara `reference_time` e `knowledge_cutoff`. Onde a fonte não
   permite reconstrução histórica demonstrável, o provider não emite estado atual como
   fato histórico: produz lacuna/limitação determinística e a Policy falha fechada quando
   esse fato é material.
5. Assertions e contribuições usadas por seleção temporal preservam `known_at` explícito.
   Registros legados sem esse dado não recebem backfill inferido e não são selecionáveis
   como conhecimento histórico estrito.
6. Seleção de Policy e base normativa usa todos os candidatos temporalmente elegíveis;
   sobreposição ou lacuna resulta em ambiguidade/indeterminação, nunca em escolha pela
   versão mais recente.
7. Uma review positiva de captura externa exige captura íntegra, parseada e com projeção
   revisável. Respostas 404, vazias, malformadas, 4xx/5xx ou falhas de transporte não
   fundamentam confirmação positiva.

## Consequências e cortes

Os itens 1, 2 e 7 são corrigidos no corte de hardening da captura externa. O item 3 exige
configuração operacional e prova de deploy separada. Os itens 4 a 6 serão implementados
em cortes temporais pequenos: primeiro bloqueio fail-closed do provider, depois
`known_at` sanitário, seleção de Policy e, por último, conexão controlada da coverage
NEXT-01 ao fluxo real. Histórico material de Animal, stay e demais estados exige desenho
por fonte; não será inventado nesta correção.

Cada corte usa banco descartável, Organizations A/B, identificadores recém-semeados e
casos T0/T1/T2. Deve provar isolamento, recusa de escrita, ausência de conhecimento
posterior e preservação de Evaluation/Decision/Dossier históricos.

## Alternativas rejeitadas

- Confiar apenas no serviço para isolamento: rejeitada; falha para writers internos e não
  protege contra mudança futura de endpoint.
- Preencher `known_at` de legado a partir de `recorded_at`: rejeitada; fabricaria prova
  temporal não existente.
- Recalcular passado a partir das projeções atuais: rejeitada pela ADR-0052.
- Escolher a maior versão de Policy quando há sobreposição: rejeitada pela ADR-0041.
