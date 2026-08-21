# BuyerPolicy Fase 3 — Requisitos & Arquitetura

**Data:** 21 de agosto de 2026  
**Status:** 🔵 PLANNING  
**Versão:** ADR-0066 (em rascunho)

---

## Executive Summary

Fase 3 expande compartilhamento bilateral (Fase 2) com **feedback estruturado** (Decision/Proposal), **composição com matriz regulatória**, e **rate-limiting**. Mantém o princípio de isolamento: cada Organization acessa apenas dados que lhe foram compartilhados ou que possui.

---

## 1. Decision/Proposal Bilaterais (Feedback Estruturado)

### Problema
Fase 2 produz avaliação, mas sem mecanismo para fornecedor contestar ou escalar resultado.

### Solução Proposta

#### 1.1 Criar `SharedDecision` (analogia a `Decision`, mas para contexto compartilhado)

**Entidade:**
```python
@dataclass(frozen=True, slots=True)
class SharedDecision:
    """Decisão sobre avaliação compartilhada entre comprador e fornecedor."""
    
    decision_id: TypedId  # "shared_decision"
    grant_id: UUID  # Qual grant contextualiza essa decisão
    evaluation_id: TypedId  # Referência à avaliação original (Fase 2)
    
    # Proposta do fornecedor
    proposer_organization_id: OrganizationId  # Quem está propondo (supplier)
    proposal_content: str  # "Estou fora de carência conforme certificado X"
    proposal_evidence_references: list[str]  # URLs/IDs de suporte
    proposed_at: datetime
    
    # Revisão do comprador
    reviewer_organization_id: OrganizationId  # Comprador
    review_decision: str  # APROVADA | REJEITADA | REAVALIACAO_NECESSARIA
    review_content: str  # Justificativa
    reviewed_at: datetime | None = None
    
    # Metadados
    status: str  # PROPOSTA | REVISADA | ENCERRADA
    created_by: str
    record_owner_organization_id: OrganizationId  # RLS: sempre grant.owner_organization_id
```

#### 1.2 Endpoints

**POST /v1/rule-governance/policies/shared-policies/{policy_id}/propose**
```json
{
  "grant_id": "uuid",
  "evaluation_id": "uuid",
  "proposal_content": "Estou fora de carência...",
  "evidence_references": ["doc-123", "cert-456"]
}
```
- Permissão: `POLICY_COMPARTILHAMENTO_LER` (beneficiary)
- Validação: grant ativo, evaluation existe e pertence ao grant
- Retorna: SharedDecision com status=PROPOSTA

**POST /v1/rule-governance/policies/shared-policies/{policy_id}/decisions/{decision_id}/review**
```json
{
  "decision": "APROVADA | REJEITADA | REAVALIACAO_NECESSARIA",
  "review_content": "Certificado válido. Consentimos em..."
}
```
- Permissão: `POLICY_COMPARTILHAMENTO_LER` (owner)
- Atualiza status → REVISADA
- Retorna: SharedDecision com reviewed_at preenchido

**GET /v1/rule-governance/policies/shared-policies/{policy_id}/decisions**
- Lista todas as SharedDecisions para um grant
- Permissão: `POLICY_COMPARTILHAMENTO_LER` (owner ou beneficiary)

### Casos de Uso

| Ator | Ação | Fluxo |
|------|------|-------|
| Fornecedor | Avalia contra Policy compartilhada | POST /shared-policies/{id}/evaluate → NAOCONFORM |
| Fornecedor | Quer contestar | POST .../propose com evidência |
| Comprador | Revê proposta | POST .../review com decisão |
| Ambos | Veem histórico | GET .../decisions |

---

## 2. Composição com Matriz Regulatória (ADR-0044)

### Problema
Hoje Policy contratual é isolada da matriz de elegibilidade. Fase 3 compõe ambas.

### Solução Proposta

#### 2.1 Expandir Avaliação Compartilhada para Incluir Matriz

**Novo campo em avaliação compartilhada:**
```python
class SharedPolicyEvaluationResponse(BaseModel):
    evaluation_id: str
    policy_id: str
    origin: str  # "CONTRACT"
    
    # Resultado contra Policy contratual (Fase 2)
    result: str  # CONFORM | NAOCONFORM | INDETERMINADA
    rule_results: list[dict]
    
    # NOVO: Resultado contra matriz regulatória (se demandado)
    regulatory_matrix_evaluation: Optional[dict] = None  # {market: str, status: str, gaps: list}
    
    # Composição (novo)
    composite_verdict: Optional[str] = None  # ELEGIVEL | INELEGIVEL | REQUER_REVISAO
    composite_reasoning: Optional[str] = None
```

#### 2.2 Dois Fluxos Possíveis

**Fluxo A: Composição Transparente (Recomendado)**
- Fornecedor avalia contra Policy compartilhada (POST /shared-policies/{id}/evaluate)
- Sistema automaticamente compõe com matriz do mercado relevante
- Retorna composite_verdict (ELEGIVEL = passou contrato E matriz)

**Fluxo B: Composição Explícita (Seguro)**
- Fornecedor avalia contra Policy compartilhada (resultado isolado)
- Comprador chama endpoint separado: POST /shared-policies/{id}/compose-with-matrix
- Retorna composite_verdict apenas (sem expor matriz internamente)

### Semântica

| Contrato | Matriz | Composto |
|----------|--------|----------|
| CONFORM | ELEGIVEL | ELEGIVEL ✓ |
| CONFORM | INELEGIVEL | INELEGIVEL ✗ |
| NAOCONFORM | ELEGIVEL | INELEGIVEL ✗ |
| NAOCONFORM | INELEGIVEL | INELEGIVEL ✗ |
| INDETERMINADA | * | REQUER_REVISAO ? |

---

## 3. Rate-Limiting & Auditoria (Risco Table)

### Problema
Risco baixo apontado: "Força bruta de avaliações para derivar dataset".

### Solução Proposta

#### 3.1 Rate-Limit por Grant

**Implementação:**
```python
@dataclass(frozen=True, slots=True)
class GrantRateLimit:
    grant_id: UUID
    evaluations_per_minute: int = 10  # Configurável
    last_evaluation_timestamp: datetime
    evaluation_count_this_minute: int
```

**Verificação:**
- POST /shared-policies/{id}/evaluate valida rate limit antes de executar
- Retorna 429 (Too Many Requests) se excedido
- Mensagem: "Limite de {N} avaliações por minuto atingido. Tente novamente em {X}s."

#### 3.2 Auditoria de Acesso

**Nova tabela: `core_audit.shared_policy_access_log`**
```sql
CREATE TABLE core_audit.shared_policy_access_log (
    access_id UUID PRIMARY KEY,
    grant_id UUID NOT NULL,
    organization_id UUID NOT NULL,  -- Quem acessou
    action VARCHAR(50),  -- "READ" | "EVALUATE" | "PROPOSE" | "REVIEW"
    policy_id UUID NOT NULL,
    subject_type VARCHAR(50),  -- Para EVALUATE
    subject_id UUID,
    http_status_code INT,
    accessed_at TIMESTAMP WITH TIME ZONE,
    record_owner_organization_id UUID NOT NULL,
    
    FOREIGN KEY (grant_id) REFERENCES core_audit.authorization_grants(grant_id),
    FOREIGN KEY (organization_id) REFERENCES core_identity.organizations(organization_id)
);
```

**Registro automático:**
- Cada POST/GET em /shared-policies/* cria entry no log
- Inclui status code (200, 403, 429, etc.)
- Comprador pode listar: GET /v1/rule-governance/policies/{id}/access-log

---

## 4. Avaliação com Sujeitos de Outra Organization

### Problema
Fase 2: Fornecedor só consegue avaliar seus próprios sujeitos.  
Fase 3: Comprador consegue solicitar avaliação ou fornecedor compartilha seus sujeitos também?

### Solução Proposta: **Opção A (Segura)**

Fornecedor continua avaliando seus próprios sujeitos. Comprador não avalia sujeitos do fornecedor unilateralmente.

**Justificativa:**
- Mantém isolamento (cada org acessa apenas seus dados)
- Evita exposição de dataset completo do fornecedor
- Mais simples implementar RLS

**Possível Fase 4:** Se demanda explícita, permitir "FieldScope expansion" onde fornecedor compartilha também seus sujeitos (novo grant type: BILATERAL_DATA_SHARING).

---

## 5. Proteger contra Expiração de Grant

### Problema
Ao expirar grant, avaliações/decisions ficam "órfãs". Fornecedor perde acesso a histórico.

### Solução Proposta

#### 5.1 Snapshot Automático

**Ao criar Decision/Proposal:**
- Capturar e preservar uma cópia da Policy (sem regras internacionais, apenas definição)
- Armazenar em `SharedDecision.policy_snapshot_json`
- Fornecedor continua vendo conteúdo mesmo após expiração

#### 5.2 Acesso Pós-Expiração (Leitura Apenas)

**Nova permissão:** `POLICY_COMPARTILHAMENTO_HISTORICO_LER`

**GET /v1/rule-governance/policies/shared-policies/{policy_id}/history** (post-expiration)
- Retorna apenas policy_snapshot_json (sem reexecução)
- Válido 90 dias após expiração (configurável)
- Registrado em audit log

---

## 6. Decisões de Design

### D1: Quem cria SharedDecision?

**Decisão: Apenas fornecedor (beneficiary)**
- Fornecedor propõe (status=PROPOSTA)
- Comprador aprova/rejeita (status=REVISADA)
- Evita assimetria (comprador não consegue criar proposta em nome do fornecedor)

### D2: Evaluation é mutável?

**Decisão: Não, imutável (ADR-0052)**
- SharedDecision referencia Evaluation, não a modifica
- Histórico completo preserved forever
- Se reavaliação necessária, criar nova Evaluation

### D3: Rate-Limit é global ou por grant?

**Decisão: Por grant**
- Diferentes grants podem ter diferentes limites
- Permite "VIP" grants com limite maior (contrato premium)
- Simples audit

### D4: Composição é obrigatória?

**Decisão: Não, opcional**
- Fornecedor vê resultado contra contrato
- Comprador opta por compor com matriz (endpoint separado)
- Não expõe lógica interna de matriz

---

## 7. Dependências & Pré-requisitos

- ✅ ADR-0050 (Execução determinística) — em vigor
- ✅ ADR-0044 (Matriz regulatória) — em vigor
- ✅ ADR-0052 (Temporalidade, Evaluation imutável) — em vigor
- ✅ ADR-0065 (BuyerPolicy Fase 2, Grant bilateral) — implementado
- ⏳ ADR-0066 (BuyerPolicy Fase 3) — em rascunho neste documento

---

## 8. Escopo de BUILD

### Incremento 1: Decision/Proposal (3-4 dias)
1. Domain model: `SharedDecision`
2. Repository: `TransactionalSharedDecisionRepository` (6 métodos)
3. Service: `SharedDecisionService.create_proposal()`, `.review_proposal()`
4. 3 endpoints HTTP (create, review, list)
5. Testes: 8-10 casos (propose sem grant, review com status, list filtering)

### Incremento 2: Rate-Limiting & Auditoria (2 dias)
1. `GrantRateLimit` (em-memory ou Redis?)
2. `SharedPolicyAccessLog` table + migration
3. Validação em POST /shared-policies/{id}/evaluate
4. GET /v1/rule-governance/policies/{id}/access-log endpoint
5. Testes: 5-6 casos (excede limite, logged correctly, histórico)

### Incremento 3: Composição com Matriz (2-3 dias)
1. Expandir `SharedPolicyEvaluationResponse` com `regulatory_matrix_evaluation`
2. Chamar ADR-0044 internamente (reutilizar `MarketEligibilityMatrix`)
3. Novo endpoint ou flag no POST /shared-policies/{id}/evaluate
4. Testes: 4-5 casos (compose transparent, explicit, different verdicts)

### Incremento 4: Snapshot & Acesso Pós-Expiração (1-2 dias)
1. `policy_snapshot_json` em `SharedDecision`
2. Nova permissão `POLICY_COMPARTILHAMENTO_HISTORICO_LER`
3. GET /history endpoint
4. Testes: 3 casos (snapshot captured, accessible post-expiry, expires)

**Total Estimado:** 8-12 dias (4 incrementos parallelizáveis em 2 sprints)

---

## 9. Riscos Mitigados

| Risco | Mitigation |
|-------|-----------|
| Exposição dataset fornecedor | Só fornecedor avalia seus sujeitos (Opção A) |
| Força bruta de avaliações | Rate-limit por grant + audit log |
| Perda de histórico pós-expiração | Snapshot automático + acesso 90d |
| Composição expõe matriz | Endpoint separado (Fluxo B) |
| Assimetria decision ownership | Apenas beneficiary cria proposal |

---

## 10. Próximos Passos

### Imediato (Esta semana)
1. ✅ Validar Requisitos com Product/Compliance
2. ✅ Responder as 5 questões críticas (D1-D5 acima)
3. ✅ Redator ADR-0066 (aprovação)

### Planning (Próxima semana)
1. Decompor incrementos em tasks
2. Estimar burn-down
3. Agendar kick-off de BUILD

### BUILD (Fase 3 Incremento 1 em paralelo com Fase 2 validation)

---

## Apêndice: Perguntas Respondidas

| Pergunta | Resposta | Decisão |
|----------|----------|---------|
| Quem cria SharedDecision? | Fornecedor apenas | D1 |
| Evaluation mutável? | Não (ADR-0052) | D2 |
| Rate-limit escopo? | Por grant | D3 |
| Composição obrigatória? | Não, opcional | D4 |
| Sujeitos cross-org? | Não, Opção A (Fase 4?) | Seção 4 |

