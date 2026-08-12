# NEXT-07 — Market Change Impact e Reavaliação: Design Package

**Data:** 12 de agosto de 2026  
**Estado:** AGUARDANDO REVISÃO HUMANA  
**Escopo:** identificar impacto de mudança normativa sobre conclusões existentes; não altera conclusão histórica nem inicia processamento em massa no primeiro corte.

## Objetivo

Transformar uma mudança de Policy em pergunta auditável:

```text
Policy MARKET_TEST_A v1 → v2
             ↓
quais Decisions foram produzidas sob v1?
             ↓
quais podem requerer nova avaliação sob v2?
             ↓
qual é a diferença entre a projeção anterior e a nova, quando reavaliada?
```

O resultado nunca reescreve `Evaluation`, `Decision`, `Dossier` ou `VerificationBundle` históricos. `REASSESSMENT_REQUIRED` é estado da leitura/planejamento; não é `DecisionResult`, não é inelegibilidade e não é comando operacional.

## Decisão proposta

Reutilizar a seleção temporal de Policy do NEXT-02, `Decision`/`Evaluation` imutáveis, `NormativeBasisSnapshot`, `MarketReadiness` e o mecanismo existente de outbox/inbox somente em corte posterior e explicitamente aprovado.

Não criar agora `PolicyChange`, `ImpactAssessment` ou `ReevaluationJob` persistidos. O primeiro corte deve ser um assessment puro e sintético, com entrada explícita de Policy anterior/nova e conclusões históricas fornecidas.

## Invariantes

1. Policy nova nunca muda resultado, hash, snapshot ou Dossier de Decision antiga.
2. Impacto potencial não é reprovação, autorização, mudança de mercado ou nova Decision.
3. O assessment compara contextos preservados; não reexecuta Rule nem infere resultado sob a Policy nova.
4. Somente Decisions da mesma Organization, finalidade e Policy de origem podem aparecer no conjunto.
5. `reference_time`, `knowledge_cutoff`, Policy/version e boundary devem constar do resultado.
6. Uma mudança em `MARKET_TEST_A` não produz impacto para outro perfil/mercado.
7. Reconhecimento externo continua `INTERNAL_ONLY`; impacto não amplia essa fronteira.

## Contrato conceitual do Corte 1

```text
MarketChangeImpactRequest
  organization
  purpose
  previous_policy id/version
  replacement_policy id/version
  reference_time
  knowledge_cutoff
  recognition_boundary = INTERNAL_ONLY
  historical Decision/Evaluation pairs

MarketChangeImpactAssessment
  context anterior e novo
  affected entries
  unaffected entries
  reassessment_required_count
  exclusions / limitations
  result_boundary = MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION
```

Uma entrada é potencialmente afetada quando a Decision/Evaluation histórica corresponde exatamente à Policy anterior e à finalidade solicitada. Decisões de outra Policy, finalidade, Organization ou sem anchor normativo preservado ficam fora do conjunto ou aparecem como limitação explícita; jamais são tratadas como impacto confirmado.

## Cortes

### Corte 1 — análise pura de impacto

- contratos transitórios de Application e serviço puro;
- caso sintético `MARKET_TEST_A v1 → v2`;
- classificar `AFFECTED`, `UNRELATED`, `LIMITED` sem nova Evaluation/Decision;
- contagens e referências individuais determinísticas;
- testes de isolamento de mercado, Policy, Organization, tempos, snapshots legados e imutabilidade.

### Corte 2 — planejamento persistido, se demonstrado necessário

- somente se a análise precisar sobreviver a uma sessão ou ser revisada/aprovada;
- decidir ADR antes de identidade, ciclo de vida, RLS, retenção e auditoria de `ImpactAssessment`/plano;
- ainda sem reavaliação automática.

### Corte 3 — execução assíncrona controlada

- após contrato aprovado de reavaliação, usar outbox/worker existentes como transporte, sem confundi-los com autoridade normativa;
- cada nova execução emite nova Evaluation/Decision/Dossier independentes;
- idempotência por subject + Policy + reference time + knowledge cutoff;
- resultados parciais, falhas e reprocessamento ficam explícitos.

## Testes mínimos do Corte 1

1. v1 → v2 identifica somente Decisions de `MARKET_TEST_A v1` como potencialmente afetadas;
2. Decision histórica v1 mantém hash e resultado após o assessment;
3. Decision de `MARKET_TEST_B`, outra finalidade ou outra Organization não entra no impacto;
4. Policy/tempo/boundary ambíguos ou snapshot legado não se tornam impacto positivo;
5. o assessment não cria Evaluation, Decision, Dossier, mensagem de outbox ou alteração em lote;
6. ordem distinta das entradas produz o mesmo relatório.

## Fora do escopo

- mercado real, mudança regulatória real, interpretação jurídica ou notificação externa;
- API, migration, fila, worker, outbox, reavaliação automática e processamento em massa;
- reserva/seleção de lote e composição com estabelecimento/operação;
- SISBOV, GTA, Odoo e simulador;
- relatório “antes/depois” como fato confirmado antes de novas Decisions existirem.

## Portão para autorizar somente o Corte 1

1. primeiro caso é `MARKET_TEST_A v1 → v2`, sintético e `INTERNAL_ONLY`;
2. impacto é assessment transitório, sem persistência, API ou worker;
3. nenhuma Rule é reexecutada e nenhuma conclusão histórica é modificada;
4. `AFFECTED` significa somente “reavaliação potencialmente necessária”;
5. nenhuma integração externa, mercado real ou composição operacional entra no corte.

## Contratos respeitados

- **ADR-0041/0044:** elegibilidade é contextual; matriz e reavaliação são projeções, não mudança de `DecisionResult`.
- **NEXT-02:** Policy e base normativa são temporais e preservadas na Evaluation.
- **NEXT-03/05/06:** boundary, Dossier individual e readiness continuam derivados e limitados ao contexto Titan.
- **ADR-0006/0038:** outbox e worker podem transportar execução futura, mas não criam autoridade, impacto ou efeito externo por si.
