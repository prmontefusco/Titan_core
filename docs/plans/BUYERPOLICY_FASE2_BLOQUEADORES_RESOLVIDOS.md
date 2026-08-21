# BuyerPolicy Fase 2 — Bloqueadores Resolvidos

**Data:** 21 de agosto de 2026  
**Status:** ✅ RESOLVIDOS - Pronto para Testes Realistas

---

## Bloqueador 1: source_type para CONTRACT

### ❌ Problema Inicial
Indefinição sobre como representar o source_type para Rules de compartilhamento (CONTRACT).

### ✅ Resolução
Encontrado em `packages/core_domain/rule_governance.py:13`:

```python
class RuleSourceType(Enum):
    CONTRACT = "contrato"
```

**Via HTTP (testes):**
```python
"source_type": "contrato"  # string literal
```

**Via Python (domínio):**
```python
RuleSourceType.CONTRACT  # enum
```

### Aplicação na Implementação
A função helper `_contract_policy_real()` em testes realistas deve usar:

```python
"source_type": "contrato"  # linha ~170 do test_policy_sharing_api_realistic.py
```

---

## Bloqueador 2: Padrão de Criação de Rules

### ❌ Problema Inicial  
Confirmação de que `/rule-identities + /versions` é o padrão correto (vs. endpoint `/rules` desconhecido).

### ✅ Resolução
Confirmado em documentação de pesquisa anterior:

1. `POST /v1/rule-governance/rule-identities` → cria RuleIdentity
2. `POST /v1/rule-governance/rule-identities/{id}/versions` → publica RuleVersion
3. Policy é associada na etapa 2 via campo `policy_id` no JSON

**Fonte:** `test_policy_governance_api.py:34-60` — padrão validado em testes de integração.

### Aplicação na Implementação
A função `_contract_policy_real()` segue exatamente este fluxo (linhas 162-197 do documento de pesquisa).

---

## 📋 Próximos Passos

Ambos os bloqueadores resolvidos. Pronto para implementação de testes realistas:

1. ✅ Criar `_contract_policy_real()` helper
2. ✅ Criar `test_compartilhamento_e_avaliacao_fluxo_completo()`
3. ✅ Adicionar testes parametrizados (negação, expiração, heterogeneidade)
4. ✅ Validar RLS com grants revogados/expirados

---

## Evidência

**Commit base:** ff83f60  
**Arquivo:** packages/core_domain/rule_governance.py:10-17  
**Padrão:** test_policy_governance_api.py:43-61
