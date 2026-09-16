# BuyerPolicy Fase 3 — Incremento 4 — Snapshot e Historico Pos-Expiracao

Data: 2026-09-16

Status: PROCEED para BUILD

## Contexto

ADR-0066 decidiu que a Fase 3 inclui preservacao de historico pos-expiracao: o
fornecedor nao deve perder a leitura do criterio que usou em uma autoavaliacao
compartilhada apenas porque o grant expirou. Incrementos 1, 2 e 3 ja foram
entregues; o Incremento 4 nao foi iniciado.

## Objetivo

Preservar um snapshot minimo da Policy contratual no momento em que o fornecedor
cria uma `SharedDecision`, e expor esse historico por endpoint proprio mesmo apos
expiracao do grant.

## Fora de escopo

- reabrir grant expirado para nova leitura da Policy viva;
- permitir nova avaliacao, composicao ou revisao apos expiracao;
- expor facts, snapshot de facts, `rule_results`, evidencias brutas ou matriz
  regulatoria do comprador;
- criar Dossier ou VerificationBundle;
- alterar o fluxo de `/evaluate`, `/compose-with-matrix` ou `/decisions` ja
  entregue.

## Decisoes de implementacao

1. O snapshot fica em `core_audit.shared_decisions.policy_snapshot_json`.
2. O snapshot e capturado na criacao da proposta, sob contexto do owner do grant,
   e contem somente definicao da Policy e Rules contratuais publicadas/ativas
   naquele momento.
3. O endpoint novo e:

   `GET /v1/rule-governance/policies/shared-policies/{policy_id}/history`

4. O endpoint devolve somente `SharedDecision` da Policy em que a Organization
   ativa e proponente ou revisora. Isso preserva o isolamento existente e permite
   historico pos-expiracao sem depender de grant ativo.
5. Ausencia de snapshot em registros antigos nao reabre Policy viva: o item e
   retornado com `policy_snapshot=None`.

## Arquivos previstos

- `packages/core_domain/policy_sharing.py`
- `packages/core_infrastructure/persistence/shared_decision.py`
- nova migration Core/Audit
- `packages/core_application/shared_decision_service.py`
- `apps/api/policy_governance.py`
- `tests/integration/test_policy_sharing_api.py`
- `apps/validacao/buyerpolicy_shared_decision.py`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md`

## Testes previstos

- criar proposta retorna snapshot preenchido;
- `/history` continua disponivel ao beneficiario depois de expirar o grant;
- `/shared-policies/{policy_id}` continua fechado depois de expirar o grant;
- terceira Organization nao enxerga historico;
- owner tambem enxerga historico das propostas da Policy.
