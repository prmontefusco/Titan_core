# BuyerPolicy — Fase 1: Design Package (PLAN)

**Data:** 2026-08-19
**Estado:** AGUARDANDO APROVAÇÃO PARA BUILD
**Escopo:** desenho técnico da SPEC aprovada de BuyerPolicy Fase 1 — nenhuma linha de código, migration ou teste é criada por este documento.
**Derivado de:**

- [ADR-0064](/C:/programing/Titan/docs/adr/0064-buyerpolicy-elegibilidade-especifica-do-comprador.md) — ACEITA em 2026-08-19 (corrigida nesta mesma revisão, §9, quanto a capabilities server-side)
- [SPEC aprovada](/C:/programing/Titan/docs/specs/approved/2026-08-19-buyerpolicy-fase-1-policy-interna-do-comprador.md) — aprovada em 2026-08-19

> Por que este PLAN existe antes do BUILD: a ADR-0064 decide a fronteira de produto (`INTERNAL_POLICY`, `INTERNAL_ONLY`, sem atravessar Organizations). Mas o PLAN — obrigatório antes de qualquer código, per `docs/specs/README.md` — revelou que a premissa de "nenhuma capability nova" da ADR estava tecnicamente imprecisa: não existe hoje nenhuma rota HTTP genérica para acionar `PolicyEvaluationService`. Isso introduz uma `Permission` nova (`POLICY.AVALIAR`) e uma rota nova de contrato público — o que, per `DEVELOPMENT.md`, é categoria **RED** (autorização, contrato público) e exige decisão humana explícita antes do BUILD, mesmo com a SPEC já aprovada.

---

## 1. Objetivo

Transformar a SPEC aprovada em um desenho técnico executável: arquivos exatos, contratos de request/response, pontos de verificação de invariante, e critério de erro — proporcional ao nível CRITICAL da SPEC, sem introduzir nenhuma decisão de produto nova além do que a ADR-0064 já aceitou.

## 2. Entradas

Documentos: ADR-0064, SPEC aprovada, `DEVELOPMENT.md`, `docs/specs/README.md`.

Código inspecionado nesta revisão do PLAN (achados reportados na ADR-0064 §9):

- `packages/core_domain/policy.py`, `packages/core_domain/rule.py`, `packages/core_domain/rule_governance.py`
- `packages/core_application/policy_service.py`, `policy_authorization.py`, `rule_governance_service.py`, `rule_governance_authorization.py`
- `packages/core_application/evaluation_service.py` (`PolicyEvaluationService.evaluate_policy`, `RuleEvaluationEngine`)
- `apps/api/policy_governance.py`, `apps/api/livestock_rule_governance.py`, `apps/api/livestock_dependencies.py` (`require_permission`, `typed_id_or_problem`)
- `apps/api/livestock_queries.py` (endpoints de elegibilidade existentes, todos hardcoded a fluxos regulatórios)
- `packages/core_infrastructure/persistence/rule.py` (`TransactionalRuleRepository.list_by_policy`), `persistence/rule_governance.py`, `persistence/policy.py`
- `tests/api/test_core_public_surface.py` (portão de superfície pública), `tests/integration/test_policy_governance_api.py`, `tests/integration/test_rule_governance_api.py`
- `apps/validacao/governanca_regras.py`
- `docs/CHECKLIST_DE_IMPLEMENTACAO.md` — Passo 6.1/6.2 e NEXT-08/NEXT-08b (precedente direto: rota de Policy nasceu sob `/v1/rule-governance/policies` por decisão arquitetural já registrada, não CRUD solto do Core)

## 3. Achado central: link real entre Policy e Rule

`RuleAdoption` **não** é o link consumido pela avaliação. `RuleAdoption` registra que uma Organization adotou uma `RuleVersion`/template para uma finalidade operacional (auditoria/governança, ADR-0043) e é **opcional** — `PublicarVersaoRegraRequest.create_adoption` é um flag booleano. O link real usado por `PolicyEvaluationService.evaluate_policy(policy, rules, snapshot, purpose, ...)` é `Rule.policy_id`, atribuído no momento em que a `RuleVersion` é publicada (`PublicarVersaoRegraRequest.policy_id`).

Consequência direta para o desenho: a verificação de homogeneidade de origem (ADR-0064 Invariante 3) e a montagem do conjunto de Rules para avaliação usam `TransactionalRuleRepository.list_by_policy(policy_id)`, **não** uma consulta por `RuleAdoption`.

## 4. Contrato técnico proposto

### 4.1 Permission nova

```text
POLICY.AVALIAR
```

Segue o padrão `<SUBSTANTIVO>.<VERBO>` já usado por `POLICY.CRIAR/PUBLICAR/LER` (`policy_authorization.py`) e `RULE_GOVERNANCE.*`. Adicionada a `POLICY_PERMISSIONS` em `policy_authorization.py`. Concedida ao operador e a qualquer Organization com `Membership`/`Role` equivalente — nenhuma restrição de "tipo comprador" (ADR-0064 §3).

### 4.2 Rota nova

```text
POST /v1/rule-governance/policies/{policy_id}/evaluate
```

Mesmo prefixo de `policy_governance.py`, pelo mesmo motivo já registrado no cabeçalho daquele arquivo (`test_endpoints_de_dominio_do_core_continuam_fechados` proíbe CRUD solto de primitiva do Core; a rota nasce a serviço do caso de uso de governança de regras). Arquivo proposto: `apps/api/policy_governance.py` (extensão do router existente) — não um arquivo novo, para não fragmentar o mesmo recurso em dois routers.

**Request (`AvaliarPolicyRequest`):**

```text
subject_type: str        # tipo já suportado pelo FactProviderPort da vertical (ex.: "animal")
subject_id: str          # TypedId do sujeito, mesma Organization do solicitante
purpose: str              # finalidade declarada da avaliação (livre, auditável — não confundir com AccessPurpose)
reference_time: datetime | None   # ADR-0052; default = agora
```

**Response (`PolicyEvaluationResponse`):**

```text
evaluation_id, snapshot_hash, context_hash
policy_id, policy_code, policy_version
outcome: EvaluationOutcome
rule_results: [...]
origin: "INTERNAL_POLICY"          # derivado, homogêneo (secao 4.3)
recognition_boundary: "INTERNAL_ONLY"   # derivado enquanto origin == INTERNAL_POLICY
owner_organization_id                    # Organization proprietária da Policy
requesting_organization_id               # Organization ativa no pedido (== owner nesta fase)
```

`origin` e `recognition_boundary` são **strings controladas**, não persistidas como campo novo em `Policy` (ADR-0064 Decisão 2/4: valor derivado, não schema novo) — resolve a pergunta aberta nº3 da SPEC sem exigir migration nem alteração de `DOMAIN.md`.

### 4.3 Verificação de homogeneidade de origem (ADR-0064 Invariante 3)

Dois pontos de verificação (defesa em profundidade — resolve a pergunta aberta nº2 da SPEC):

1. **Na publicação da `RuleVersion`** (`RuleGovernanceService.publish_rule_version`, `packages/core_application/rule_governance_service.py`): antes de vincular a nova `RuleVersion` ao `policy_id` informado, buscar as `Rule`s já publicadas daquela Policy (`list_by_policy`), resolver a `RuleIdentity` de cada uma (por `organization_id` + `code`) e comparar `source_type`. Mismatch rejeita a publicação com motivo estruturado — é o ponto que impede a Policy de nascer heterogênea.
2. **Na avaliação** (rota nova, 4.2): antes de chamar `PolicyEvaluationService.evaluate_policy`, repetir a mesma verificação sobre o conjunto de `Rule`s carregado. Mismatch nunca resulta em avaliação parcial silenciosa — recusa a operação inteira com `CONTRACT_VIOLATION` (ADR-0050 §11).

Ambos os pontos reutilizam a mesma função pura de verificação (`packages/core_application/`, local exato a decidir no BUILD entre `rule_governance_service.py` e um módulo novo pequeno compartilhado — não é decisão de produto, fica para o BUILD).

### 4.4 Origem "BuyerPolicy" vs. Policy regulatória

Uma Policy só é reconhecida como BuyerPolicy — e só recebe `recognition_boundary=INTERNAL_ONLY` na resposta — quando **todas** as suas Rules publicadas têm `RuleIdentity.source_type == INTERNAL_POLICY`. Uma Policy com `LAW`/`REGULATION`/`CERTIFICATION`/`TITAN_TEMPLATE` (mesmo isolada) responde com `origin=NAO_CLASSIFICADO_COMO_BUYERPOLICY` e seu resultado **não** é elegível para a rota de avaliação de BuyerPolicy — a rota rejeita com `CONTRACT_VIOLATION` explícito, não silenciosamente reclassifica. Isso é o mecanismo concreto que impede a "mistura semântica" apontada pela Discovery.

## 5. Persistência e migration

**Nenhuma migration.** `Policy`, `Rule`, `RuleIdentity`, `RuleAdoption` e `Evaluation` já existem com as colunas necessárias (`organization_id`, `policy_id`, `source_type`). `origin`/`recognition_boundary` são calculados em memória na resposta, não persistidos — consistente com ADR-0064 §21 ("persistir `recognition_boundary` só se `BILATERAL_CONTRACTUAL` existir").

## 6. Erros e negação segura (ADR-0027, `DOMAIN.md` P-198)

| Situação | Resposta |
|---|---|
| `Permission POLICY.AVALIAR` ausente no próprio `OrganizationContext` | `403 PERMISSAO_AUSENTE` |
| `policy_id` inexistente ou de outra Organization | `404 RECURSO_NAO_ENCONTRADO` (uniforme, igual a `policy_governance.py` hoje) |
| `subject_id` inexistente ou de outra Organization | `404 RECURSO_NAO_ENCONTRADO` (mesmo padrão) |
| Policy com Rules de `source_type` heterogêneo | `422`/`CONTRACT_VIOLATION`, motivo estruturado, sem avaliação parcial |
| Policy em `DRAFT`/`REVOKED` | erro já coberto por `PolicyEvaluationService` (`ValueError` → `422`) |
| Fact ausente no snapshot | `RuleResult.PENDENTE`/`INDETERMINADA` (ADR-0050, comportamento já existente do engine) |

Nenhum desses casos usa um código de status que diferencie, para quem não tem acesso, "existe mas não é seu" de "não existe" (ver critério de aceite 9 da SPEC).

## 7. Testes mínimos (para o BUILD, não executados neste PLAN)

1. Publicar `RuleVersion` `INTERNAL_POLICY` sob Policy que já tem `RuleVersion` `LAW` → rejeitado.
2. Publicar `RuleVersion` `INTERNAL_POLICY` sob Policy nova/vazia → aceito.
3. Avaliar BuyerPolicy homogênea sobre subject visível → `Evaluation` com `origin=INTERNAL_POLICY`, `recognition_boundary=INTERNAL_ONLY`.
4. Avaliar Policy heterogênea (burlando o gate de publicação via fixture direta) → rota recusa com `CONTRACT_VIOLATION`, não avalia parcialmente.
5. Organization B tentando avaliar `policy_id` de Organization A → `404` uniforme.
6. Organization B tentando avaliar `subject_id` de Organization A → `404` uniforme.
7. Sem `POLICY.AVALIAR` → `403`, sem revelar existência do `policy_id`/`subject_id`.
8. Revogar `Policy`/`RuleVersion` e reavaliar → nova `Evaluation` reporta ausência explícita; `Evaluation` anterior mantém hash e resultado.
9. `Evaluation` de BuyerPolicy nunca aparece em `GET` da matriz `MarketEligibilityPurpose` (ADR-0044) e vice-versa — teste de não-interferência.
10. `test_superficie_publica_do_core_esta_congelada` atualizado com a rota nova (mesmo portão usado em NEXT-08).

Roteiro `apps/validacao`: estender `governanca_regras.py` (ou script irmão dedicado) cobrindo os casos 1, 3, 5, 6, 7, 8 fim a fim via HTTP real.

## 8. Fora de escopo (reafirmado)

Idêntico à SPEC §"Fora de escopo": `RuleSourceType.CONTRACT`, `Sharing`/`AuthorizationGrant`/`AccessPurpose`/`FieldScope` novos, avaliação de dado de terceiro, `Decision`/`DecisionProposal`/`DecisionAuthorityProfile`, composição com Policy regulatória, UI, alteração de `DOMAIN.md`/`ARCHITECTURE.md`.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Gate de homogeneidade checado só num dos dois pontos por erro de implementação | Teste 4 força o caminho de avaliação a recusar mesmo se o gate de publicação falhar |
| `origin`/`recognition_boundary` calculados de forma inconsistente entre resposta de avaliação e futura leitura de Policy | Função pura única, testada isoladamente, reutilizada nos dois lugares |
| Rota nova ampliar superfície pública sem revisão | `test_superficie_publica_do_core_esta_congelada` já é o portão que obriga decisão explícita (mesmo mecanismo do NEXT-08) |
| Confundir esta rota com a matriz de elegibilidade regulatória | Nome de rota, campo `origin` explícito e teste 9 (não-interferência) |

## 10. Portão para autorizar o BUILD

Este PLAN só autoriza BUILD quando o decisor confirmar, explicitamente, os itens que `DEVELOPMENT.md` classifica como RED (autorização e contrato público) e que a SPEC/ADR não haviam antecipado em detalhe:

1. Nome e formato da `Permission` nova: `POLICY.AVALIAR`.
2. Caminho e verbo da rota nova: `POST /v1/rule-governance/policies/{policy_id}/evaluate`.
3. Local do gate de homogeneidade: publicação da `RuleVersion` **e** avaliação (defesa em profundidade), não apenas um dos dois.
4. `origin`/`recognition_boundary` como campos derivados na resposta, não persistidos.

Nenhum código será escrito antes dessa confirmação.

## 11. Não implementação

Este documento não cria API, migration, teste ou UI. É desenho técnico para revisão humana, imediatamente anterior ao BUILD.
