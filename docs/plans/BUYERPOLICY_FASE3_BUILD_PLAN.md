# BuyerPolicy Fase 3 — Build Plan & Tasks

**Data:** 21 de agosto de 2026  
**Status:** 🟢 READY FOR KICK-OFF  
**Estimativa Total:** 8-12 dias (4 incrementos independentes)

---

## Overview: 4 Incrementos Parallelizáveis

```
┌─────────────────────────────────────────────────────────┐
│ INCREMENTO 1: Decision/Proposal (3-4 dias)              │
│ ├─ Domain model: SharedDecision                         │
│ ├─ Repository: TransactionalSharedDecisionRepository    │
│ ├─ Service: SharedDecisionService                       │
│ ├─ Endpoints: POST propose, POST review, GET list       │
│ └─ Tests: 8-10 cases                                    │
├─────────────────────────────────────────────────────────┤
│ INCREMENTO 2: Rate-Limiting & Auditoria (2 dias)       │
│ ├─ Model: GrantRateLimit                               │
│ ├─ Table: core_audit.shared_policy_access_log          │
│ ├─ Validation: 429 Too Many Requests                   │
│ ├─ Endpoint: GET /access-log                           │
│ └─ Tests: 5-6 cases                                    │
├─────────────────────────────────────────────────────────┤
│ INCREMENTO 3: Composição com Matriz (2-3 dias)         │
│ ├─ Expand: SharedPolicyEvaluationResponse              │
│ ├─ Lógica: Compor contrato + matriz                    │
│ ├─ Endpoint: flag ou novo /compose-with-matrix         │
│ └─ Tests: 4-5 cases                                    │
├─────────────────────────────────────────────────────────┤
│ INCREMENTO 4: Snapshot & Pós-Expiração (1-2 dias)      │
│ ├─ Field: policy_snapshot_json                         │
│ ├─ Permission: POLICY_COMPARTILHAMENTO_HISTORICO_LER   │
│ ├─ Endpoint: GET /history                              │
│ └─ Tests: 3 cases                                      │
└─────────────────────────────────────────────────────────┘
```

---

## INCREMENTO 1: Decision/Proposal (3-4 dias)

### Task 1.1: Domain Model (4 horas)

**Arquivo:** `packages/core_domain/policy_sharing.py` (novo)

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from packages.shared_kernel import OrganizationId, TypedId

@dataclass(frozen=True, slots=True)
class SharedDecision:
    """Decisão sobre avaliação compartilhada (Fase 3)."""
    
    decision_id: TypedId  # "shared_decision"
    grant_id: UUID
    evaluation_id: TypedId  # "rule_evaluation"
    
    proposer_organization_id: OrganizationId  # Beneficiary (fornecedor)
    proposal_content: str
    proposal_evidence_references: list[str]
    proposed_at: datetime
    
    reviewer_organization_id: OrganizationId  # Owner (comprador)
    review_decision: Optional[str] = None  # "APROVADA" | "REJEITADA" | "REAVALIACAO_NECESSARIA"
    review_content: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    
    status: str = "PROPOSTA"  # "PROPOSTA" | "REVISADA" | "ENCERRADA"
    created_by: str = ""
    record_owner_organization_id: OrganizationId = None  # RLS
    
    policy_snapshot_json: Optional[str] = None  # Preenchido em Incremento 4
    
    def __post_init__(self) -> None:
        if self.decision_id.entity_type != "shared_decision":
            raise ValueError("decision_id deve ser do tipo 'shared_decision'.")
        if self.status not in ("PROPOSTA", "REVISADA", "ENCERRADA"):
            raise ValueError(f"status inválido: {self.status}")
        if self.review_decision is not None and self.status != "REVISADA":
            raise ValueError("review_decision requer status=REVISADA")
```

**Checklist:**
- ✅ Domain model frozen + slots
- ✅ Validações pós-init
- ✅ Tipo "shared_decision" em decision_id
- ✅ Status enum coerente
- ✅ RLS field (record_owner_organization_id)

---

### Task 1.2: Repository (6 horas)

**Arquivo:** `packages/core_infrastructure/persistence/shared_decision.py` (novo)

**Métodos:**
1. `save(decision)` — INSERT novo
2. `get_by_id(decision_id)` — SELECT by PK
3. `get_by_evaluation_id(evaluation_id)` — Qual Decision para esta Evaluation
4. `list_by_grant(grant_id)` — Todas as Decisions de um grant
5. `update_review(decision_id, review_decision, review_content)` — Mark as REVISADA
6. `list_pending_review(owner_org_id)` — Para comprador ver propostas aguardando

**SQL:**
```sql
CREATE TABLE core_audit.shared_decisions (
    decision_id UUID PRIMARY KEY,
    grant_id UUID NOT NULL,
    evaluation_id UUID NOT NULL,
    proposer_organization_id UUID NOT NULL,
    proposal_content TEXT NOT NULL,
    proposal_evidence_references TEXT,  -- JSON array
    proposed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    reviewer_organization_id UUID NOT NULL,
    review_decision VARCHAR(50),
    review_content TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    status VARCHAR(20) NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    record_owner_organization_id UUID NOT NULL,
    policy_snapshot_json TEXT,  -- NULL now, filled in Incremento 4
    
    FOREIGN KEY (grant_id) REFERENCES core_audit.authorization_grants(grant_id),
    FOREIGN KEY (evaluation_id) REFERENCES core_evaluation.evaluations(evaluation_id),
    FOREIGN KEY (proposer_organization_id) REFERENCES core_identity.organizations(organization_id),
    FOREIGN KEY (reviewer_organization_id) REFERENCES core_identity.organizations(organization_id),
    FOREIGN KEY (record_owner_organization_id) REFERENCES core_identity.organizations(organization_id)
);
```

**Checklist:**
- ✅ TransactionalSharedDecisionRepository
- ✅ 6 métodos public
- ✅ Text SQL (não ORM)
- ✅ FK para grant, evaluation, organizations
- ✅ RLS via record_owner

---

### Task 1.3: Service & Permissions (4 horas)

**Arquivo:** `packages/core_application/shared_decision_service.py` (novo)

```python
@dataclass(frozen=True, slots=True)
class SharedDecisionService:
    """Orquestração de propostas e revisões."""
    
    decisions: TransactionalSharedDecisionRepository
    grants: TransactionalAuthorizationGrantRepository
    evaluations: Any  # TransactionalEvaluationRepository
    
    def create_proposal(
        self,
        grant_id: UUID,
        evaluation_id: TypedId,
        proposal_content: str,
        evidence_references: list[str],
        proposer_organization_id: OrganizationId,
        created_by: str,
    ) -> SharedDecision:
        """Fornecedor cria proposta (contestação/reconhecimento)."""
        # Validar: grant existe, ativo, beneficiary é proposer
        # Validar: evaluation existe, pertence ao grant
        # Criar SharedDecision status=PROPOSTA
        # Retornar
        
    def review_proposal(
        self,
        decision_id: TypedId,
        review_decision: str,  # "APROVADA" | "REJEITADA" | "REAVALIACAO_NECESSARIA"
        review_content: str,
        reviewer_organization_id: OrganizationId,
        reviewed_by: str,
    ) -> SharedDecision:
        """Comprador revê proposta do fornecedor."""
        # Validar: decision existe
        # Validar: reviewer_organization_id == grant.owner
        # Validar: status == PROPOSTA antes de revisar
        # Atualizar status=REVISADA, reviewed_at=now()
        # Retornar
```

**Permissões (package core_application/policy_authorization.py):**
- ✅ `POLICY_COMPARTILHAMENTO_PROPOR` — Fornecedor cria proposal
- ✅ `POLICY_COMPARTILHAMENTO_REVISAR` — Comprador revê

**Checklist:**
- ✅ Service com 2 métodos
- ✅ Validações: grant, evaluation, ownership
- ✅ Atomicidade: status muda com reviewed_at
- ✅ 2 novas permissions

---

### Task 1.4: HTTP Endpoints (4 horas)

**Arquivo:** `apps/api/policy_governance.py` (extend)

**Endpoint 1: POST /v1/rule-governance/policies/{policy_id}/shared-policies/{policy_id}/propose**
```python
@router.post(
    "/{policy_id}/shared-policies/{policy_id}/propose",
    response_model=SharedDecisionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Fornecedor propõe contestação/reconhecimento",
)
def propor_shared_decision(
    policy_id: str,
    corpo: CriarSharedDecisionRequest,  # grant_id, evaluation_id, content, evidence_refs
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_PROPOR))],
    connection: ConnectionDependency,
) -> SharedDecisionResponse:
    # Validação: policy_id é UUID
    # Validação: corpo tem grant_id (verifica contexto != owner)
    # Chamar service.create_proposal()
    # Retornar SharedDecisionResponse
```

**Endpoint 2: POST /v1/rule-governance/policies/{policy_id}/shared-policies/{policy_id}/decisions/{decision_id}/review**
```python
@router.post(
    "/{policy_id}/shared-policies/decisions/{decision_id}/review",
    response_model=SharedDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprador revê proposta",
)
def revisar_shared_decision(
    policy_id: str,
    decision_id: str,
    corpo: RevisarSharedDecisionRequest,  # decision, content
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_REVISAR))],
    connection: ConnectionDependency,
) -> SharedDecisionResponse:
    # Similar a propor, mas chama service.review_proposal()
```

**Endpoint 3: GET /v1/rule-governance/policies/{policy_id}/shared-policies/{policy_id}/decisions**
```python
@router.get(
    "/{policy_id}/shared-policies/decisions",
    response_model=list[SharedDecisionResponse],
    summary="Listar todas as decisões",
)
def listar_shared_decisions(
    policy_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_LER))],
    connection: ConnectionDependency,
) -> list[SharedDecisionResponse]:
    # GET list_by_grant(grant_id) where grant.policy_id == policy_id
```

**Models:**
```python
class CriarSharedDecisionRequest(BaseModel):
    grant_id: str
    evaluation_id: str
    proposal_content: str
    evidence_references: list[str] = []

class RevisarSharedDecisionRequest(BaseModel):
    review_decision: str  # "APROVADA" | "REJEITADA" | "REAVALIACAO_NECESSARIA"
    review_content: str

class SharedDecisionResponse(BaseModel):
    decision_id: str
    grant_id: str
    evaluation_id: str
    status: str
    proposed_at: datetime
    reviewed_at: Optional[datetime]
    proposal_content: str
    review_decision: Optional[str]
    review_content: Optional[str]
```

**Checklist:**
- ✅ 3 endpoints
- ✅ Modelo Request/Response limpo
- ✅ Permissões corretas
- ✅ Validações de UUID
- ✅ Prefix correto: /policies/{policy_id}/shared-policies/...

---

### Task 1.5: Testes & Integração (6 horas)

**Arquivo:** `tests/integration/test_shared_decision_api.py` (novo)

**Casos:**
1. ✅ `test_propor_sem_grant_retorna_404`
2. ✅ `test_propor_com_evaluation_inexistente_retorna_404`
3. ✅ `test_propor_como_owner_retorna_403` (só beneficiary pode propor)
4. ✅ `test_propor_valido_retorna_201_com_status_PROPOSTA`
5. ✅ `test_revisar_proposal_pendente_muda_para_REVISADA`
6. ✅ `test_revisar_como_beneficiary_retorna_403` (só owner pode revisar)
7. ✅ `test_listar_decisions_do_grant_filtra_corretamente`
8. ✅ `test_revisar_ja_revisada_retorna_409_conflito`

**Linting & Type:**
- ✅ Ruff check + format
- ✅ Mypy (636 arquivos)
- ✅ alembic check

**Checklist:**
- ✅ 8 testes
- ✅ Cobertura: happy path + erros
- ✅ Portão limpo

---

## INCREMENTO 2: Rate-Limiting & Auditoria (2 dias)

### Task 2.1: GrantRateLimit Model & Store (2 horas)

**Arquivo:** `packages/core_application/grant_rate_limiter.py` (novo)

**Modelo:**
```python
@dataclass(frozen=True, slots=True)
class GrantRateLimit:
    grant_id: UUID
    evaluations_per_minute: int = 10
    last_reset: datetime
    evaluation_count_this_minute: int = 0

class GrantRateLimiter:
    """Em-memory ou Redis-backed rate limiter por grant."""
    
    def check_and_increment(self, grant_id: UUID) -> bool:
        """Retorna True se permitem avaliar, False se excedido."""
        # Implementação
```

**Opções de Storage:**
- A. Em-memory (dict): simples, funciona para um servidor
- B. Redis: escalável, compartilhado entre servidores

**Recomendação:** Em-memory (Fase 1), Redis (Fase 3.1 se multi-servidor)

**Checklist:**
- ✅ Modelo
- ✅ check_and_increment logic
- ✅ TTL (reset a cada minuto)

---

### Task 2.2: Access Log Table & Repository (3 horas)

**Arquivo:** `packages/core_infrastructure/persistence/shared_policy_access_log.py` (novo)

**SQL:**
```sql
CREATE TABLE core_audit.shared_policy_access_log (
    access_id UUID PRIMARY KEY,
    grant_id UUID NOT NULL,
    organization_id UUID NOT NULL,  -- Quem acessou
    action VARCHAR(50) NOT NULL,  -- "READ" | "EVALUATE" | "PROPOSE" | "REVIEW"
    policy_id UUID NOT NULL,
    subject_type VARCHAR(50),
    subject_id UUID,
    http_status_code INT,
    accessed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    record_owner_organization_id UUID NOT NULL,
    
    FOREIGN KEY (grant_id) REFERENCES core_audit.authorization_grants(grant_id),
    FOREIGN KEY (organization_id) REFERENCES core_identity.organizations(organization_id),
    FOREIGN KEY (record_owner_organization_id) REFERENCES core_identity.organizations(organization_id)
);
```

**Repository (2 métodos):**
1. `log_access()` — INSERT novo
2. `list_by_grant()` — SELECT para histórico

**Checklist:**
- ✅ Tabela migrations via Alembic
- ✅ Repository
- ✅ RLS field

---

### Task 2.3: Validação em POST /evaluate (2 horas)

**Arquivo:** `apps/api/policy_governance.py` (modify avaliar_shared_policy)

```python
def avaliar_shared_policy(...) -> SharedPolicyEvaluationResponse:
    # ... código anterior ...
    
    # NOVO: Rate-limit check
    limiter = GrantRateLimiter()  # Injetar de contexto
    if not limiter.check_and_increment(grant_id):
        raise HTTPException(
            status_code=429,
            detail="Limite de avaliações por minuto atingido. Tente novamente em 45s."
        )
    
    # ... resto do código ...
    
    # NOVO: Log access
    logger = SharedPolicyAccessLogRepository(connection)
    logger.log_access(
        grant_id=grant_id,
        organization_id=contexto.organization_id,
        action="EVALUATE",
        policy_id=policy_typed_id,
        subject_type=corpo.subject_type,
        subject_id=corpo.subject_id,
        http_status_code=201,
    )
```

**Checklist:**
- ✅ Rate-limit middleware
- ✅ 429 response
- ✅ Access log INSERT
- ✅ Sem quebra de testes existentes

---

### Task 2.4: GET /access-log Endpoint (2 horas)

**Endpoint:**
```python
@router.get(
    "/{policy_id}/access-log",
    response_model=list[AccessLogResponse],
    summary="Histórico de acessos à Policy compartilhada",
)
def listar_access_log(
    policy_id: str,
    contexto: Annotated[OrganizationContext, Depends(require_permission(POLICY_COMPARTILHAMENTO_LER))],
    connection: ConnectionDependency,
) -> list[AccessLogResponse]:
    # Filtrar por policy_id
    # RLS: organizacao pode ver se é owner ou beneficiary
    # Retornar últimos 1000 (paginar se necessário)
```

**Model:**
```python
class AccessLogResponse(BaseModel):
    access_id: str
    grant_id: str
    organization_id: str  # Quem acessou
    action: str
    http_status_code: int
    accessed_at: datetime
    subject_type: Optional[str]
```

**Checklist:**
- ✅ Endpoint GET
- ✅ RLS respeitado
- ✅ Paginação básica

---

### Task 2.5: Testes (2 horas)

**Arquivo:** `tests/integration/test_shared_policy_rate_limit.py` (novo)

**Casos:**
1. ✅ `test_avalia_dentro_do_limite_retorna_201`
2. ✅ `test_excede_limite_retorna_429`
3. ✅ `test_429_inclui_retry_after_header`
4. ✅ `test_access_log_registra_cada_avaliacao`
5. ✅ `test_listar_access_log_retorna_historico_correto`
6. ✅ `test_access_log_filtra_por_status_code`

**Checklist:**
- ✅ 6 testes
- ✅ Portão limpo

---

## INCREMENTO 3: Composição com Matriz (2-3 dias)

**Será detalhado em sessão posterior** (após Incremento 1 & 2 serem merged)

---

## INCREMENTO 4: Snapshot & Pós-Expiração (1-2 dias)

**Será detalhado em sessão posterior** (após Incremento 1 & 2 & 3)

---

## Timeline & Milestones

### Sprint 1 (Incremento 1 + 2)
- **Kickoff:** 21 de agosto de 2026
- **Termino:** ~29 de agosto
- **Deliverable:** Decision/Proposal + Rate-Limiting funcionando end-to-end

### Sprint 2 (Incremento 3 + 4)
- **Kickoff:** 30 de agosto
- **Termino:** ~6 de setembro
- **Deliverable:** Composição + Histórico, Fase 3 COMPLETA

---

## Commits & PRs Esperados

### Sprint 1
1. PR: "feat(core): SharedDecision domain + repository + service"
2. PR: "feat(api): Endpoints propose + review + list"
3. PR: "feat(core): GrantRateLimiter + access log"
4. PR: "feat(api): Rate-limit validation + access-log endpoint"

### Sprint 2
1. PR: "feat(core): Composição com matriz regulatória"
2. PR: "feat(core): SharedDecision snapshot + histórico pós-expiração"

---

## Portão de Verificação

Cada incremento deve passar:
- ✅ pytest (fixtures reais)
- ✅ ruff check + format
- ✅ mypy (636 arquivos)
- ✅ alembic check
- ✅ Sem breaking changes em Fase 2

---

## Questões em Aberto

1. **Rate-limiter storage:** Em-memory ou Redis?
   - Decision: Em-memory (Fase 1), considerar Redis em Fase 3.1
2. **Composição UI:** Transparente (automática) ou explícita (novo endpoint)?
   - Decision (27 ago 2026): **Fluxo B — explícita, por endpoint separado.** Confirma D4 e a
     tabela de riscos ("Composição expõe matriz → endpoint separado"); o §2.2 do REQUIREMENTS,
     que marcava o Fluxo A como recomendado, fica superado. O fornecedor não vê o efeito da
     matriz do comprador.
   - Bloqueio (27 ago 2026): o Incremento 3 não começa antes da ADR-0068 — a autoavaliação
     compartilhada da Fase 2 é um stub e não há resultado contratual real para compor.
3. **Access-log retention:** Limpar após 90 dias?
   - Decision: SIM, adicionar job de limpeza em Fase 3.1

