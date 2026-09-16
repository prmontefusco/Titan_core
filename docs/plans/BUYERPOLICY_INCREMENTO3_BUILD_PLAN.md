# BuyerPolicy Fase 3 — Incremento 3 (Composição com Matriz) — Plan

**Data:** 16 de setembro de 2026
**Escopo:** `docs/plans/BUYERPOLICY_FASE3_BUILD_PLAN.md` deixou o Incremento 3 deliberadamente não detalhado
("será detalhado em sessão posterior"). A `ADR-0066` já decidiu o essencial — Fluxo B, D1-D5, contrato
público — mas não resolveu detalhes de implementação que exigem ler o código real (que não existia quando a
ADR foi escrita). Este documento resolve esses detalhes antes do BUILD, seguindo `DEVELOPMENT.md`.

---

## O que já está decidido (não reaberto aqui)

- Endpoint `POST /v1/rule-governance/policies/shared-policies/{policy_id}/compose-with-matrix`, chamado pelo
  **comprador** (owner do grant), nunca pelo fornecedor.
- D4: composição é opcional e explícita — nunca automática no `/evaluate`.
- Resposta contém **apenas `composite_verdict`** (`ELEGIVEL | INELEGIVEL | REQUER_REVISAO`) — "sem expor
  matriz internamente" (REQUIREMENTS §2.2, ADR-0066 risco "composição expõe matriz").
- Semântica: contrato `CONFORM` + matriz `ELEGIVEL` → `ELEGIVEL`; qualquer reprovação → `INELEGIVEL`;
  qualquer indeterminação → `REQUER_REVISAO`.

## Decisões resolvidas nesta sessão (lendo o código real)

### 1. Mapeamento de enums reais (REQUIREMENTS usava nomes placeholder)

`Evaluation.outcome` é `EvaluationOutcome` (`packages/core_domain/evaluation.py`), não `CONFORM`/
`NAOCONFORM` como o REQUIREMENTS presumia. Mapeamento adotado:

| `EvaluationOutcome` (contrato) | Tratado como |
|---|---|
| `CONDICOES_SATISFEITAS` | passou |
| `CONDICOES_NAO_SATISFEITAS` | reprovado |
| qualquer outro (`INFORMACAO_INSUFICIENTE`, `EVIDENCIA_CONFLITANTE`, `VALIDACAO_EXTERNA_PENDENTE`, `REVISAO_HUMANA_NECESSARIA`, `INDETERMINADO`) | indeterminado |

`MarketEligibilityStatus` (`packages/livestock_application/market_eligibility.py`) para o mercado pedido:

| `MarketEligibilityStatus` (matriz) | Tratado como |
|---|---|
| `ELEGIVEL` | passou |
| `NAO_ELEGIVEL` | reprovado |
| `CONDICIONADO`, `INDETERMINADO`, `AUSENTE` | indeterminado |

Composto: reprovado em qualquer lado → `INELEGIVEL`; nenhum reprovado mas algum indeterminado →
`REQUER_REVISAO`; os dois passaram → `ELEGIVEL`.

### 2. A matriz é sempre avaliada para todos os mercados — o request precisa dizer qual

`MarketEligibilityService.evaluate()` sempre roda `self.profiles` inteiro (todos os mercados,
`DEFAULT_MARKET_PROFILES`) e devolve uma entrada por mercado. Não existe "avaliar só um mercado". Por isso o
request de compose-with-matrix inclui `market` (um código de `MarketEligibilityPurpose`, ex.
`"exportacao-uniao-europeia"`) e o handler extrai a entrada correspondente do resultado — o resto da matriz
nunca sai da função.

### 3. Rodar a matriz para o Animal do fornecedor **persiste** Evaluation/Decision reais — decisão: aceitar

Confirmado lendo `market_eligibility.py:1004,1019`: quando a avaliação independente por mercado roda com
`evaluation_repository`/`decision_repository` configurados (o mesmo caminho que
`POST /animals/{id}/eligibility/market-matrix` já usa), ela **persiste** uma `Evaluation` e uma `Decision`
regulatórias reais, sob a Organization avaliada.

Isso não é um efeito colateral inventado por este corte — é exatamente o que aconteceria se o próprio
fornecedor chamasse a matriz diretamente. Rodando sob o contexto do fornecedor (a mesma troca de contexto que
`avaliar_shared_policy` já faz), a `Evaluation`/`Decision` nascem sob a Organization dele, na mesma trilha de
auditoria que qualquer avaliação regulatória sua. O comprador nunca vê o conteúdo — só o `composite_verdict`.

**Decisão: aceitar a persistência.** Impedir a persistência exigiria o modo `base_result` do serviço (que
pressupõe uma Decision **já existente** para reaproveitar — não é o caso aqui) e contradiz o próprio
propósito de compose-with-matrix: produzir um veredito real, não uma prévia hipotética.

**Fora de escopo, por decisão explícita:** `LivestockDossierTemplate`/`DossierService` (o Dossier formal que
`executar_matriz_de_mercado` constrói) não é chamado aqui — nenhum caso de uso pediu um Dossier para uma
composição de terceiro, e criar um seria abstração sem uso demonstrado.

### 4. Isolamento reaproveita exatamente o padrão de `avaliar_shared_policy` (ADR-0068)

1. Sob contexto do comprador: ler o `grant` por `grant_id`; confirmar `owner_organization_id == contexto.
   organization_id` (só o comprador compõe — diferente de `/evaluate`, que é do fornecedor) e grant `ATIVO`/
   não expirado.
2. Verificar cota do grant (D3) — **mesmo limiter e mesma chave** de `avaliar_shared_policy`
   (`shared_policy_evaluation_rate_limiter()`/`shared_policy_evaluation_key(grant.grant_id)`): compose é mais
   uma forma de sondar o fornecedor sob o mesmo grant, não merece orçamento próprio.
3. Trocar para o contexto do fornecedor (`grant.beneficiary_organization_id`) — só então ler a `Evaluation`
   contratual (por `evaluation_id`, deve pertencer a essa Organization e a essa Policy — mesma checagem que
   `SharedDecisionService.create_proposal` já faz) e rodar a matriz para o `subject_id` da própria
   `Evaluation` (não é preciso pedir `animal_id` no request — evita expor mais do que o necessário).
4. Nenhum `rule_results` (nem do contrato, nem da matriz) sai da função — só o `composite_verdict`.
5. Registrar acesso (`_registrar_acesso_compartilhado`) com nova `action="COMPOSE"`.

### 5. Novos artefatos de contrato

- `packages/core_domain/policy_sharing.py`: `SHARED_POLICY_ACCESS_ACTION_COMPOSE = "COMPOSE"`, adicionado a
  `VALID_SHARED_POLICY_ACCESS_ACTIONS`.
- `packages/core_application/policy_authorization.py`: `POLICY_COMPARTILHAMENTO_COMPOR`, adicionada a
  `POLICY_PERMISSIONS`. Only o comprador usa; a checagem de "é o owner" é em código (mesmo padrão de D1/D5),
  não em papel — os dois lados de teste recebem a mesma permissão, como já ocorre para as demais.
- `apps/api/policy_governance.py`: `ComposeComMatrizRequest{grant_id, evaluation_id, market}`,
  `ComposeComMatrizResponse{grant_id, evaluation_id, market, composite_verdict}`, endpoint
  `compor_shared_policy_com_matriz`.

### 6. Erros

| Condição | Resposta |
|---|---|
| grant inexistente/não pertence à Policy | 404 `RECURSO_NAO_ENCONTRADO` |
| quem chama não é o owner do grant | 403 `GRANT_INVALIDO` (mesmo reason code já usado para grant inválido em `avaliar_shared_policy`, por consistência) |
| grant não `ATIVO`/expirado | 403 `GRANT_INVALIDO` |
| cota excedida | 429 `LIMITE_DE_AVALIACOES_EXCEDIDO` (mesmo formato, com `Retry-After`) |
| `market` não é um `MarketEligibilityPurpose` válido | 422 `PARAMETRO_INVALIDO` |
| `Evaluation` não encontrada ou não pertence ao grant/policy | 404 `RECURSO_NAO_ENCONTRADO` |
| `MarketEligibilityService` levanta `HumanReviewRequired` | não é erro — tratado como `REQUER_REVISAO` (é exatamente a semântica de indeterminação que já mapeamos) |

## Testes previstos

`tests/integration/test_shared_decision_api.py` (estende o arquivo existente da Fase 3) ou novo arquivo:

1. Comprador compõe com contrato `CONDICOES_SATISFEITAS` + matriz `ELEGIVEL` → `ELEGIVEL`.
2. Contrato `CONDICOES_NAO_SATISFEITAS` → `INELEGIVEL` independente da matriz.
3. Matriz `NAO_ELEGIVEL` (contrato ok) → `INELEGIVEL`.
4. Matriz `INDETERMINADO`/`AUSENTE` (contrato ok) → `REQUER_REVISAO`.
5. Fornecedor (beneficiary) tentando compor → 403.
6. Grant expirado/revogado → 403.
7. `market` inválido → 422.
8. Cota do grant já esgotada (mesma chave do `/evaluate`) → 429.
9. Resposta não contém `rule_results` nem detalhamento por mercado (prova de não-vazamento).

## Fora de escopo (reafirmado)

Dossier/VerificationBundle para o resultado composto; Incremento 4 (snapshot/pós-expiração); Fase 4
(sujeitos cross-Organization); qualquer alteração ao comportamento de `/evaluate` (D4: nunca automático).
