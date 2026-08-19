# BuyerPolicy Fase 2 — BUILD Resumo de Progresso

**Sessão 1 Status:** PROGRESSO CHECKPOINT  
**Data:** 2026-08-19  
**Commit Checkpoint:** 452ca63

---

## O Que Foi Feito

✅ **DISCOVERY** (concluído)
- Caso real bilateral validado: comprador compartilha Policy contratual, fornecedor autoavalia

✅ **ADR-0065** (ACEITA)
- 7 decisões RED explicitadas e aprovadas
- Permissions, endpoints, grant anchor, persistência, validade, AccessPurpose, FieldScope

✅ **PLAN** (pronto)
- Design Package com 19 seções, ownership técnico, modelo, auditoria, riscos

✅ **SPEC** (APROVADA)
- 8 passos de fluxo, 5 cenários de erro, 14 critérios de aceite

✅ **BUILD Fase 1**
- `packages/core_infrastructure/persistence/authorization_grant.py` (TransactionalAuthorizationGrantRepository, Protocol, 6 métodos)
- `packages/core_application/policy_sharing_service.py` (PolicySharingService, create_grant, get_active_grant, revoke_grant com validações)
- `packages/core_application/policy_authorization.py` (+3 Permissions: COMPARTILHAR, COMPARTILHAMENTO_LER, AVALIAR_COMPARTILHADA)

---

## O Que Falta (Sessão 2)

⏳ **Endpoints HTTP** (apps/api/policy_governance.py)

```python
# POST /v1/rule-governance/policies/{policy_id}/shares
# Request: beneficiary_organization_id, access_purpose, valid_until, field_scope_profile
# Response: grant_id, policy_id, owner_organization_id, beneficiary_organization_id, status, valid_from, valid_until

# POST /v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke
# Request: revocation_reason (opcional)
# Response: grant_id, status=REVOGADO, revoked_at, revoked_by, revocation_reason

# GET /v1/rule-governance/shared-policies/{policy_id}
# Response: policy_id, code, version, origin="CONTRACT", rules[], grant_id, owner_organization_id

# POST /v1/rule-governance/shared-policies/{policy_id}/evaluate
# Request: subject_type, subject_id, purpose, reference_time
# Response: evaluation_id, policy_id, origin="CONTRACT", outcome, rule_results, missing_facts, hashes
```

⏳ **Migration Alembic**

```sql
CREATE TABLE core_identity.authorization_grants (
    grant_id UUID PRIMARY KEY,
    owner_organization_id UUID NOT NULL,
    beneficiary_organization_id UUID NOT NULL,
    policy_id UUID NOT NULL,
    policy_version_id UUID NOT NULL,
    access_purpose VARCHAR(100) NOT NULL,
    field_scope_profile VARCHAR(100) NOT NULL,
    valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255) NOT NULL,
    revoked_at TIMESTAMP NULL,
    revoked_by VARCHAR(255) NULL,
    revocation_reason TEXT NULL,
    record_owner_organization_id UUID NOT NULL
);
```

⏳ **Testes Unitários** (tests/application/test_policy_sharing_service.py)

- create_grant com Policy homogeneamente CONTRACT → sucesso
- create_grant com Policy INTERNAL_POLICY → rejeitado 422
- create_grant com Policy heterogênea → rejeitado 422
- create_grant com valid_until no passado → rejeitado
- revoke_grant com owner correto → sucesso
- revoke_grant com owner incorreto → rejeitado

⏳ **Testes Integração** (tests/integration/test_policy_sharing_api.py)

- POST /shares: criar grant válido
- POST /shares: rejeitar Policy não-contratual
- GET /shared-policies: ler Policy com grant válido
- GET /shared-policies: 404 sem grant
- GET /shared-policies: 403 com grant expirado
- POST /shared-policies/evaluate: avaliar conforme
- POST /shared-policies/evaluate: avaliar não-conforme
- POST /shared-policies/evaluate: avaliar com dados faltantes
- POST /shares/{grant_id}/revoke: revogar grant
- POST /shared-policies: 404 após revogação
- Terceira Organization recebe 404 uniforme
- Avaliação compartilhada não entra em MarketEligibilityPurpose
- Fase 1 (POLICY.AVALIAR) continua funcionando

⏳ **Portão de Qualidade**

- `python -m uv run --locked ruff check .`
- `python -m uv run --locked ruff format --check .`
- `python -m uv run --locked mypy`
- `python -m uv run --locked pytest` (deve passar com +14 testes novos)

⏳ **Commit Final**

```
feat(core): BuyerPolicy Fase 2 — endpoints, migration, testes (ADR-0065, BUILD completo)

Implementa compartilhamento bilateral de Policy contratual.
...
```

---

## Dependências/Acoplamentos

- ✅ `policy_authorization.py` — já tem import das 3 Permissions
- ✅ `policy_sharing_service.py` — usa `PolicyEvaluationService`, `PolicyOrigin`, já existentes
- ✅ `authorization_grant.py` — isolado, nenhuma mudança necessária em outro arquivo
- ⏳ `policy_governance.py` — precisa importar `PolicySharingService`, `AuthorizationGrant`, as 3 Permissions
- ⏳ `livestock_api_support.py` — precisa adicionar as 3 Permissions ao operador de teste
- ⏳ `test_core_public_surface.py` — precisa adicionar os 4 endpoints novos à lista congelada

---

## Decisões Já Travadas (Não Reabrir)

- ✅ Grant anchor: Policy + versão (resolvido em authorization_grant.py)
- ✅ Persistência: tabela própria (migration já descrita acima)
- ✅ valid_until obrigatório (validado em policy_sharing_service.py)
- ✅ AccessPurpose local (definido como "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR")
- ✅ FieldScope mínimo (apenas Policy, Rule, condições, resultado, razões, facts faltantes)

---

## Prompt para Sessão 2

```
Sessão 2: Completar BUILD de BuyerPolicy Fase 2

Estado inicial: Commit 452ca63, com persistence + service + permissions prontos.

Tarefas:
1. Adicionar 4 endpoints em apps/api/policy_governance.py
   (ver SPEC item 8.1-8.4 para contratos exatos)

2. Criar migration alembic para tabela authorization_grants
   (ver resumo acima para schema)

3. Adicionar testes unitários em tests/application/test_policy_sharing_service.py
   (6 casos descritos acima)

4. Adicionar testes integração em tests/integration/test_policy_sharing_api.py
   (13 casos descritos acima)

5. Atualizar imports/permissions em:
   - tests/livestock_api_support.py (adicionar 3 Permissions ao PERMISSOES_OPERADOR)
   - tests/api/test_core_public_surface.py (adicionar 4 endpoints à SUPERFICIE_ESPERADA)

6. Rodar portão de qualidade:
   - ruff check
   - ruff format
   - mypy
   - pytest

7. Commit final com mensagem descrevendo tudo acima

Referências:
- ADR-0065: docs/adr/0065-buyerpolicy-fase-2-compartilhamento-contratual.md
- PLAN: docs/plans/BUYERPOLICY_FASE2_DESIGN_PACKAGE.md
- SPEC: docs/specs/proposed/2026-08-19-buyerpolicy-fase-2-compartilhamento-contratual.md
- Código base: persistence (authorization_grant.py) e service (policy_sharing_service.py) já no repo
```

---

## Estado do Repositório

- **Branch:** main
- **Último commit:** 452ca63 (BuyerPolicy Fase 2 arquitetura + skeleton)
- **Uncommitted:** nenhum
- **Status:** limpo, pronto para Sessão 2
