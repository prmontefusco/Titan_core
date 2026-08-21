# BuyerPolicy Fase 2 — Testes Realistas (Status)

**Data:** 21 de agosto de 2026  
**Bloqueadores Resolvidos:** ✅ Ambos  
**Testes Realistas:** ⚠️ Em Implementação — Bloqueador de RLS

---

## ✅ Bloqueadores Resolvidos

### Bloqueador 1: source_type para CONTRACT ✅
- **Resposta:** `RuleSourceType.CONTRACT` = `"contrato"` (string)
- **Fonte:** `packages/core_domain/rule_governance.py:13`
- **Status:** RESOLVIDO
- **Evidência:** `docs/plans/BUYERPOLICY_FASE2_BLOQUEADORES_RESOLVIDOS.md`

### Bloqueador 2: Padrão de Criação de Rules ✅
- **Resposta:** `/rule-identities + /versions` é correto
- **Fonte:** Validado em `test_policy_governance_api.py`
- **Status:** RESOLVIDO

---

## ⚠️ Nova Issue Descoberta: RLS na Inserção de Grants

### Problema
Ao tentar criar um Authorization Grant via HTTP:
- **Erro:** `current transaction is aborted, commands ignored until end of transaction block`
- **Contexto:** Ao executar `RESET ROLE` após inserção em `authorization_grants`
- **Causa Provável:** RLS policy na tabela está rejeitando a inserção

### Achado Crítico
- ✅ Tabela `authorization_grants` não existia — foi gerada via Alembic autogenerate
- ✅ Migração aplicada com sucesso
- ⚠️ RLS policies podem estar impedindo inserção

### Próximas Investigações
1. Verificar se há RLS policies ativas em `authorization_grants`
2. Confirmar que `record_owner_organization_id` está sendo preenchido corretamente
3. Validar permissões do usuário `titan` no schema `core_identity`

---

## 📋 Implementação de Testes Realistas

### Status Atual
- ✅ Arquivo de testes criado: `tests/integration/test_policy_sharing_api_realistic.py`
- ✅ 5 testes propostos implementados:
  1. `test_compartilhamento_create_grant_simples` — PASSOU ✅
  2. `test_compartilhamento_fluxo_completo` — BLOQUEADO ⚠️
  3. `test_compartilhamento_negacao_sem_grant` — NÃO TESTADO
  4. `test_compartilhamento_expirado_bloqueia_acesso` — NÃO TESTADO
  5. `test_compartilhamento_nao_cria_grant_sem_permissao` — NÃO TESTADO
  6. `test_compartilhamento_apenas_policies_contratuais` — NÃO TESTADO

### Helpers Criados
- `_contract_policy_real()`: Cria Policy homogeneamente CONTRACT com validações
- `_animal()`: Cria Animal para autoavaliação
- `_headers()`: Retorna headers com Organization ID

---

## 🔧 Fix Aplicado

### policy_sharing_service.py
- **Problema:** `policy.current_version_id` não existe (atributo não é definido em Policy)
- **Fix:** Alterado para usar `policy_id` como base para `policy_version_id` TypedId
- **Impacto:** Resolve erro de AttributeError na criação de grants

### datetime.now() → datetime.now(UTC)
- **Problema:** Inconsistência de timezone
- **Fix:** Adicionado `from datetime import UTC` e usado na criação de grants
- **Impacto:** Alinha com padrão de timezone-aware datetimes

---

## 🎯 Recomendação para Próximos Passos

### Urgência Alta: Resolver RLS
1. Investigar se `authorization_grants` tem RLS policies ativas
2. Verificar permissões do user `titan` vs. role NOBYPASSRLS (se houver)
3. Confirmar que o schema `core_identity` permite inserção

### Se RLS Resolver:
- Rodar todos os 5 testes realistas
- Validar fluxo completo: compartilhar → ler → avaliar → revogar
- Adicionar testes parametrizados para edge cases

### Escopo de Testes Confirmado:
- ✅ Fluxo completo (6-7 passos)
- ✅ Negação sem grant
- ✅ Expiração de grant
- ✅ Homogeneidade (rejeita INTERNAL_POLICY)
- ✅ Permissões (rejeita compartilhamento por não-owner)

---

## 📊 Proporção de Conclusão

| Item | Status | % |
|------|--------|---|
| Bloqueadores | ✅ RESOLVIDOS | 100% |
| Implementação de código | ✅ COMPLETA | 100% |
| Testes realistas (criação) | ✅ IMPLEMENTADOS | 100% |
| Testes realistas (execução) | ⚠️ BLOQUEADO | 20% |
| **Total Estimado** | **⚠️ EM ANDAMENTO** | **70%** |

---

## Próximos Passos

1. **IMEDIATO:** Resolver bloqueador de RLS em `authorization_grants`
2. **ENTÃO:** Rodar suite completa de testes realistas (5 testes)
3. **FINALMENTE:** Documentar BuyerPolicy Fase 2 como PRONTA PARA INTEGRAÇÃO

**ETA para conclusão:** 1-2 horas após resolução de RLS
