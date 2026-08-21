# BuyerPolicy Fase 2 — Pesquisa para Testes Realistas

**Data:** 19 de agosto de 2026  
**Sessão:** Pesquisa de Exemplos Reais  
**Status:** Descoberta Completa

---

## 🔍 Descobertas

### 1. **Padrão Existente de Policy Homogênea (INTERNAL_POLICY)**

Encontrado em: `tests/integration/test_policy_governance_api.py:43`

```python
def _buyerpolicy_homogenea(ambiente, cliente, organizacao) -> str:
    """Cria, via HTTP, uma Policy + RuleIdentity(INTERNAL_POLICY) + RuleVersion
    publicadas, prontas para avaliacao. Retorna o policy_id."""
    
    # 1. Criar Policy
    headers = {"X-Titan-Organization-Id": str(organizacao.organization_id.value)}
    policy_id = str(
        cliente.post(
            "/v1/rule-governance/policies",
            headers=headers,
            json={
                "code": f"buyerpolicy-{uuid4().hex[:8]}",
                "name": "Criterio interno do comprador",
            },
        ).json()["policy_id"]
    )
    
    # 2. Criar RuleIdentity (INTERNAL_POLICY)
    identity = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-buyerpolicy-{uuid4().hex[:8]}",
            "purpose": "Elegibilidade interna do comprador.",
            "scope": "livestock.animal",
            "source_type": "politica_interna",  # INTERNAL_POLICY
            "vertical": "livestock",
            "description": "Criterio proprio do comprador.",
        },
    ).json()
    
    # 3. Publicar RuleVersion
    cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Fora de carencia",
            "conditions": [_CONDICAO_FORA_DE_CARENCIA],
            "justification": "Criterio interno do comprador.",
        },
    )
    
    # 4. Publicar Policy
    cliente.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})
    return policy_id
```

**Achado:** Este padrão funciona perfeitamente. Pode ser adaptado para **CONTRACT** apenas mudando `source_type`.

---

### 2. **Padrão de Condição Real**

Encontrado em: `tests/integration/test_policy_governance_api.py:16`

```python
_CONDICAO_FORA_DE_CARENCIA = {
    "fact_type": "livestock.withdrawal",
    "payload_key": "in_withdrawal",
    "operator": "equals",
    "expected_value": False,
    "description": "Nao pode estar em carencia no momento da avaliacao.",
}
```

**Achado:** Condições reais usam facts de `livestock.*` que já têm dados no sistema.

---

### 3. **Padrão de RuleIdentity em Testes de Domínio**

Encontrado em: `tests/application/test_rule_governance_service.py:144`

```python
identity = service.create_identity(
    organization_id=org_id,
    code="Rule-Carencia-Farmacologica",
    purpose="ELEGIBILIDADE_FARMACOLOGICA",
    scope="livestock.animal",
    source_type=RuleSourceType.INTERNAL_POLICY,  # ← Enum real
    actor=actor,
    occurred_at=datetime(2026, 7, 26, tzinfo=UTC),
)
```

**Achado:** RuleSourceType é um **enum**, não string. Exemplo: `RuleSourceType.CONTRACT` para compartilhamento.

---

### 4. **Como Criação de Animal Funciona**

Encontrado em: `tests/integration/test_policy_governance_api.py:33`

```python
def _animal(ambiente, cliente, organizacao) -> str:
    resposta = cliente.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
        headers={"X-Titan-Organization-Id": str(organizacao.organization_id.value)},
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])
```

**Achado:** A fixture `ambiente` já provê `environment.property_id`, então criar Animals é trivial.

---

## 📋 Plano Realista para Testes de Fase 2

### **Padrão Proposto (Reutilizar + Adaptar)**

```python
# tests/integration/test_policy_sharing_api_realistic.py

def _contract_policy_real(
    cliente: ClienteAutenticado,
    ambiente: Ambiente,
    conditions: list[dict] | None = None,
) -> str:
    """Cria uma Policy homogeneamente CONTRACT (reutilizando padrão INTERNAL_POLICY).
    
    Padrão:
    1. POST /policies → cria rascunho
    2. POST /rule-identities → cria Identity com source_type=CONTRACT
    3. POST /rule-identities/{id}/versions → publica Rule Version
    4. POST /policies/{id}/publish → publica Policy
    
    Retorna: policy_id pronto para compartilhamento
    """
    headers = _headers(str(ambiente.org_a.organization_id.value))
    
    # 1. Criar Policy rascunho
    policy_id = str(
        cliente.post(
            "/v1/rule-governance/policies",
            headers=headers,
            json={
                "code": f"policy-contract-{uuid4().hex[:8]}",
                "name": "Criterio contratual do comprador",
                "description": "Policy bilateral para compartilhamento com fornecedor",
            },
        ).json()["policy_id"]
    )
    
    # 2. Criar RuleIdentity (CONTRACT)
    identity = cliente.post(
        "/v1/rule-governance/rule-identities",
        headers=headers,
        json={
            "code": f"rule-contract-{uuid4().hex[:8]}",
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "scope": "livestock.animal",
            "source_type": "contrato",  # CONTRACT (adapt source_type name if needed)
            "vertical": "livestock",
            "description": "Criterio contratual a ser avaliado pelo fornecedor",
        },
    ).json()
    
    # 3. Publicar RuleVersion
    if conditions is None:
        conditions = [
            {
                "fact_type": "livestock.withdrawal",
                "payload_key": "in_withdrawal",
                "operator": "equals",
                "expected_value": False,
                "description": "Nao pode estar em carencia",
            }
        ]
    
    cliente.post(
        f"/v1/rule-governance/rule-identities/{identity['rule_identity_id']}/versions",
        headers=headers,
        json={
            "policy_id": policy_id,
            "name": "Avaliacao contratual",
            "conditions": conditions,
            "justification": "Criterio bilateral acordado em contrato",
        },
    )
    
    # 4. Publicar Policy
    cliente.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})
    return policy_id


def test_compartilhamento_e_avaliacao_fluxo_completo(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
) -> None:
    """Fluxo completo: Comprador compartilha → Fornecedor lê → Fornecedor avalia."""
    
    # Passo 1: Comprador cria Policy contratual
    policy_id = _contract_policy_real(operador, ambiente)
    
    # Passo 2: Comprador compartilha com fornecedor
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares",
        json={
            "beneficiary_organization_id": str(ambiente.org_b.organization_id.value),
            "access_purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "valid_until": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            "field_scope_profile": "CONTRATO_MINIMO",
        },
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 201
    grant_id = response.json()["grant_id"]
    
    # Passo 3: Fornecedor lê a Policy (como beneficiary)
    response = operador.get(
        f"/v1/rule-governance/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 200
    shared_policy = response.json()
    assert shared_policy["origin"] == "CONTRACT"
    
    # Passo 4: Fornecedor cria um Animal para autoavaliar
    animal_id = _animal(ambiente, operador, ambiente.org_b)
    
    # Passo 5: Fornecedor avalia seu Animal contra Policy compartilhada
    response = operador.post(
        f"/v1/rule-governance/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "animal",
            "subject_id": animal_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code == 201
    evaluation = response.json()
    assert evaluation["policy_id"] == policy_id
    assert evaluation["origin"] == "CONTRACT"
    
    # Passo 6: Comprador revoga grant
    response = operador.post(
        f"/v1/rule-governance/policies/{policy_id}/shares/{grant_id}/revoke",
        json={"revocation_reason": "Relacionamento encerrado"},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REVOGADO"
    
    # Passo 7: Fornecedor não consegue mais acessar (404 ou 403)
    response = operador.get(
        f"/v1/rule-governance/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert response.status_code in (403, 404)
```

---

## 🎯 Questões Resolvidas

| Pergunta | Resposta | Fonte |
|----------|----------|--------|
| Como criar Policy homogênea? | Usar padrão `_buyerpolicy_homogenea` adaptado para CONTRACT | test_policy_governance_api.py |
| Como criar RuleIdentity? | POST /v1/rule-governance/rule-identities com source_type | test_policy_governance_api.py |
| Qual é a fonte_type para CONTRACT? | Provavelmente "contrato" (string) ou enum RuleSourceType.CONTRACT | test_rule_governance_service.py |
| Como criar Animal para teste? | Usar pattern `_animal` com ambiente.property_id | test_policy_governance_api.py |
| Quais conditions usar? | livestock.* facts já existentes (e.g., withdrawal, weight_record) | test_policy_governance_api.py |

---

## 🚦 Próximos Passos (Confirmação Necessária)

### **Abordagem Recomendada:**

1. **Criar `_contract_policy_real()`** — helperfunction reutilizável
2. **Criar teste `test_compartilhamento_e_avaliacao_fluxo_completo()`** — valida Fase 2 completa
3. **Adaptar testes parametrizados** — múltiplas conditions, múltiplas Organizations
4. **Validar RLS** — confirmar que grant expirado/revogado bloqueia acesso

### **Bloqueadores Identificados:**

1. **Nome correto de source_type para CONTRACT** — precisa confirmar se é string "contrato" ou enum
2. **Se POST /rule-governance/rules endpoint existe** — testes antigos usavam esse endpoint (não funciona)
   - Solução: usar /rule-identities + /versions (padrão real)

---

## 📊 Escopo de Testes Realistas

**3-4 testes principais:**
1. ✅ Fluxo completo: compartilhar → ler → avaliar → revogar
2. ✅ Negação: fornecedor não consegue ler sem grant
3. ✅ Expiração: grant expirado bloqueia acesso
4. ✅ Heterogeneidade: Policy mista (CONTRACT + INTERNAL) é rejeitada

**Estimativa:** ~2-3 horas de implementação
