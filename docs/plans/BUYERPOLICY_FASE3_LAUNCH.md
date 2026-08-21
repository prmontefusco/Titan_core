# BuyerPolicy Fase 3 — Launch Summary

**Data:** 21 de agosto de 2026  
**Status:** 🟢 READY FOR KICK-OFF  
**ADR:** ADR-0066 (em rascunho)  
**Timeline:** 16 dias (Sprint 1 + Sprint 2)

---

## Executive Summary

**Fase 3 expande compartilhamento bilateral com feedback estruturado, composição regulatória e rate-limiting.**

### O que muda
- ✅ **Feedback estruturado:** Fornecedor pode propor contestações via `SharedDecision`
- ✅ **Composição com matriz:** Avaliação contratual compõe com elegibilidade regulatória
- ✅ **Rate-limiting:** Proteção contra força bruta; auditoria de acesso
- ✅ **Histórico pós-expiração:** Snapshot de Policy preservado por 90 dias

### Princípios mantidos
- ✅ Isolamento: Cada org acessa apenas dados compartilhados + seus próprios
- ✅ Imutabilidade: Evaluation nunca é modificada (Fase 2)
- ✅ RLS: `record_owner_organization_id` em todas as tabelas novas

---

## Arquitetura em 30 Segundos

```
Comprador                           Fornecedor
    │                                   │
    ├─ Compartilha Policy (grant)      │
    │                                   ├─ Avalia contra Policy
    │                                   ├─ Recebe resultado "NAOCONFORM"
    │                                   ├─ Cria Proposal contestando
    │                                   └─ Aguarda revisão
    │                                   
    ├─ Revê proposta (ReviewDecision)  │
    │                                   │
    ├─ (Opcional) Compõe com matriz    │
    │   Regulatória                    │
    │                                   │
    ├─ Revoga grant                    │
    │                                   ├─ Acessa snapshot por 90d
    │                                   └─ Histórico preservado
```

---

## Entregáveis da Fase 3

### Incremento 1: Decision/Proposal (3-4 dias) ⭐ CRÍTICO
**O que:** Mecanismo para fornecedor propor e comprador revisar

| Componente | Novo? | Arquivos |
|---|---|---|
| Domain: `SharedDecision` | ✅ | `packages/core_domain/policy_sharing.py` |
| Repository: `TransactionalSharedDecisionRepository` | ✅ | `packages/core_infrastructure/persistence/shared_decision.py` |
| Service: `SharedDecisionService` | ✅ | `packages/core_application/shared_decision_service.py` |
| Endpoints | ✅ | 3 rotas em `apps/api/policy_governance.py` |
| Permissions | ✅ | 2 novas: POLICY_COMPARTILHAMENTO_PROPOR/REVISAR |
| Tests | ✅ | `tests/integration/test_shared_decision_api.py` (8 casos) |

**Outputs:**
- `POST /v1/rule-governance/.../propose` — Fornecedor cria proposta
- `POST /v1/rule-governance/.../decisions/{id}/review` — Comprador revê
- `GET /v1/rule-governance/.../decisions` — Listar todas
- `core_audit.shared_decisions` table

---

### Incremento 2: Rate-Limiting & Auditoria (2 dias) ⭐ IMPORTANTE
**O que:** Proteção contra força bruta + trilha completa de acesso

| Componente | Novo? | Arquivos |
|---|---|---|
| Rate Limiter (em-memory) | ✅ | `packages/core_application/grant_rate_limiter.py` |
| Access Log Table | ✅ | `core_audit.shared_policy_access_log` |
| Access Log Repository | ✅ | `packages/core_infrastructure/persistence/shared_policy_access_log.py` |
| Validation in POST /evaluate | ✏️ | Modifica `apps/api/policy_governance.py` |
| Endpoint GET /access-log | ✅ | `apps/api/policy_governance.py` |
| Tests | ✅ | `tests/integration/test_shared_policy_rate_limit.py` (6 casos) |

**Outputs:**
- `GET /v1/rule-governance/.../access-log` — Histórico de acessos
- Rate-limit de 10 avaliações/minuto por grant
- 429 "Too Many Requests" quando excedido
- `core_audit.shared_policy_access_log` table

---

### Incremento 3: Composição com Matriz (2-3 dias) ⭐ VALOR
**O que:** Avaliação contratual compõe com matriz regulatória

**Plano:** Será detalhado após Incremento 1 & 2 serem merged

| Componente | Status |
|---|---|
| Expand `SharedPolicyEvaluationResponse` | Pendente |
| Chamar ADR-0044 internamente | Pendente |
| Novo endpoint ou flag | Pendente |
| Tests | Pendente |

---

### Incremento 4: Snapshot & Pós-Expiração (1-2 dias) ⭐ FEATURE
**O que:** Fornecedor acessa Policy por 90d após expiração de grant

**Plano:** Será detalhado após Incremento 1 & 2 & 3 serem merged

| Componente | Status |
|---|---|
| `policy_snapshot_json` field | Pendente |
| GET /history endpoint | Pendente |
| Permission: POLICY_COMPARTILHAMENTO_HISTORICO_LER | Pendente |
| Tests | Pendente |

---

## Timeline Executivo

### Sprint 1: Semanas 1-2 (21 ago — 5 set)
```
Seg  Ter  Qua  Qui  Sex  Seg  Ter  Qua  Qui  Sex
Incremento 1: Decision/Proposal
[-D1-][-D2-][-D3-][-D4-]
        Incremento 2: Rate-Limiting
            [-D1-][-D2-]
```

**Entrega Sprint 1:** Decision/Proposal + Rate-Limiting operacionais

### Sprint 2: Semanas 3-4 (6 set — 19 set)
```
Seg  Ter  Qua  Qui  Sex  Seg  Ter  Qua  Qui  Sex
Incremento 3: Composição
[-D1-][-D2-][-D3-]
        Incremento 4: Snapshot
            [-D1-][-D2-]
```

**Entrega Sprint 2:** Composição + Histórico, Fase 3 COMPLETA

---

## Dependências & Pré-requisitos

| Pré-requisito | Status | Impacto |
|---|---|---|
| ✅ ADR-0050 (Execução determinística) | ✅ Vigente | Reutiliza RuleEvaluationEngine |
| ✅ ADR-0044 (Matriz regulatória) | ✅ Vigente | Usa MarketEligibilityMatrix (Incremento 3) |
| ✅ ADR-0052 (Temporalidade, Evaluation imutável) | ✅ Vigente | Garante snapshots válidos |
| ✅ ADR-0065 (BuyerPolicy Fase 2) | ✅ Implementado | Base: grants e compartilhamento |

**Nenhum pré-requisito bloqueador.**

---

## Riscos Mitigados

| Risco | Fase 2 | Fase 3 |
|---|---|---|
| Força bruta de avaliações | ❌ Nenhuma proteção | ✅ Rate-limit 10/min |
| Sem feedback do fornecedor | ❌ Avaliação silenciosa | ✅ Proposta + Revisão |
| Perda de histórico pós-expiração | ❌ Órfão | ✅ Snapshot 90d |
| Sem composição regulatória | ❌ Isolado | ✅ Compõe com matriz |
| Sem auditoria de acesso | ❌ Caixa preta | ✅ Access log completo |

---

## Success Criteria

Fase 3 está COMPLETA quando:

1. ✅ Fornecedor consegue propor contestação em < 100ms
2. ✅ Comprador consegue revisar e vê status REVISADA em < 100ms
3. ✅ Rate-limit bloqueia 11ª avaliação com 429
4. ✅ Access-log registra cada POST/GET automaticamente
5. ✅ Composição com matriz retorna verdict ELEGIVEL | INELEGIVEL | REQUER_REVISAO
6. ✅ Snapshot preserva Policy por 90 dias após expiração
7. ✅ Todos os 35+ testes passam
8. ✅ Ruff + Mypy + alembic check limpos
9. ✅ Sem breaking changes em Fase 2
10. ✅ 4 PRs mergeados em main

---

## Documentação Criada

✅ Nesta sessão (21 de agosto):
- `BUYERPOLICY_FASE3_DISCOVERY.md` — Requisitos iniciais
- `BUYERPOLICY_FASE3_REQUIREMENTS.md` — **Requisitos detalhados (este arquivo)**
- `BUYERPOLICY_FASE3_BUILD_PLAN.md` — **Tasks & milestones**
- `BUYERPOLICY_FASE3_LAUNCH.md` — **Sumário executivo (este arquivo)**

✅ Durante BUILD Sprint 1:
- ADR-0066 (BuyerPolicy Fase 3) — Formalizar decisões de design
- Migration Alembic para core_audit.shared_decisions + shared_policy_access_log

---

## Próximos Passos (Hoje, 21 de agosto)

### 1️⃣ Validação Rápida
- [ ] Revisar `BUYERPOLICY_FASE3_REQUIREMENTS.md` (15 min)
- [ ] Confirmar decisões D1-D5 com Product/Compliance (30 min)
- [ ] Responder questões em Aberto (seção 10)

### 2️⃣ Kick-off Sprint 1
- [ ] Designar developer para Incremento 1
- [ ] Designar developer para Incremento 2
- [ ] Setup: branches, labels, milestones no GitHub
- [ ] Primeira daily standup

### 3️⃣ Monitorar Fase 2 em Paralelo
- [ ] Validação de Fase 2 em staging (iniciada outro developer)
- [ ] Feedback de users sobre compartilhamento bilateral
- [ ] Bugs encontrados em Fase 2 = prioridade (pode bloquear Fase 3)

---

## Questões para Alinhamento Final

| Pergunta | Opção | Recomendação |
|----------|-------|-------------|
| **D1** Quem cria SharedDecision? | Apenas beneficiary | ✅ Recomendado (assimetria clara) |
| **D2** Evaluation é mutável? | Não (ADR-0052) | ✅ Recomendado (imutabilidade) |
| **D3** Rate-limit escopo? | Por grant | ✅ Recomendado (granular + simples) |
| **D4** Composição obrigatória? | Não, opcional | ✅ Recomendado (flexibilidade) |
| **D5** Sujeitos cross-org? | Não (Opção A) | ✅ Recomendado (segurança) |

---

## Métricas de Sucesso (Pós-Fase 3)

- **Tempo de proposta:** Fornecedor cria proposal em < 1 segundo (P95)
- **Taxa de rejeição:** < 5% de proposals rejeitadas (indicador de comunicação)
- **Taxa de rate-limit:** 0.1% das avaliações excedem limite (proteção ativa)
- **Acessibilidade pós-expiração:** 100% dos fornecedores conseguem ler snapshot
- **SLA de revisão:** Comprador revê em < 24h (métrica de operação)

---

## Recomendações Finais

1. **Paralelizar Incrementos 1 & 2:** Independentes, podem rodar em paralelo
2. **Confirmar decisões D1-D5:** Antes de começar Task 1.1 (hoje)
3. **Planning de Incremento 3 depois:** Quando Incremento 1 & 2 estiverem 80%
4. **Testar Fase 2 em paralelo:** Risco baixo, mas necessário antes de Fase 3 ir produção
5. **Comunicar decisões ao time:** Especialmente sobre Opção A (sujeitos cross-org não suportados)

---

## Contato & Responsabilidades

- **Product Owner:** Validar decisões D1-D5 + dar feedback
- **Architect:** Revisar ADR-0066 + guiar integração com ADR-0044
- **Dev Sprint 1:** Incrementos 1 & 2 (2 devs em paralelo)
- **QA:** Criar plano de testes além da cobertura automática
- **DevOps:** Setup de staging para Fase 3 + rate-limit infra (Redis, se necessário)

---

**Status:** 🟢 READY FOR KICK-OFF

**Next Action:** Validar decisões hoje → Kick-off Sprint 1 amanhã (22 agosto)

