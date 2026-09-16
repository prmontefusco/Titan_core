"""Governanca bilateral de Policies compartilhadas."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc

SHARED_DECISION_ENTITY_TYPE = "shared_decision"
SHARED_DECISION_STATUS_PROPOSTA = "PROPOSTA"
SHARED_DECISION_STATUS_REVISADA = "REVISADA"
SHARED_DECISION_REVIEW_APROVADA = "APROVADA"
SHARED_DECISION_REVIEW_REJEITADA = "REJEITADA"
SHARED_DECISION_REVIEW_REAVALIACAO_NECESSARIA = "REAVALIACAO_NECESSARIA"

VALID_SHARED_DECISION_STATUSES = frozenset(
    {SHARED_DECISION_STATUS_PROPOSTA, SHARED_DECISION_STATUS_REVISADA}
)
VALID_SHARED_DECISION_REVIEW_DECISIONS = frozenset(
    {
        SHARED_DECISION_REVIEW_APROVADA,
        SHARED_DECISION_REVIEW_REJEITADA,
        SHARED_DECISION_REVIEW_REAVALIACAO_NECESSARIA,
    }
)

SHARED_POLICY_ACCESS_ENTITY_TYPE = "shared_policy_access"
SHARED_POLICY_ACCESS_ACTION_READ = "READ"
SHARED_POLICY_ACCESS_ACTION_EVALUATE = "EVALUATE"
SHARED_POLICY_ACCESS_ACTION_COMPOSE = "COMPOSE"

VALID_SHARED_POLICY_ACCESS_ACTIONS = frozenset(
    {
        SHARED_POLICY_ACCESS_ACTION_READ,
        SHARED_POLICY_ACCESS_ACTION_EVALUATE,
        SHARED_POLICY_ACCESS_ACTION_COMPOSE,
    }
)


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    """Grant bilateral entre Organization owner e beneficiary."""

    grant_id: UUID
    owner_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    policy_id: TypedId
    policy_version_id: TypedId
    access_purpose: str
    field_scope_profile: str
    valid_from: datetime
    valid_until: datetime
    status: str
    created_at: datetime
    created_by: str
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revocation_reason: str | None = None
    record_owner_organization_id: OrganizationId | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from, field_name="valid_from")
        require_utc(self.valid_until, field_name="valid_until")
        require_utc(self.created_at, field_name="created_at")
        if self.revoked_at is not None:
            require_utc(self.revoked_at, field_name="revoked_at")
        if self.status not in {"ATIVO", "REVOGADO", "EXPIRADO"}:
            raise ValueError("status de AuthorizationGrant invalido.")


@dataclass(frozen=True, slots=True)
class SharedDecision:
    """Proposta e revisao sobre uma Evaluation compartilhada.

    Nao e uma Decision regulatoria do Core e nao altera a Evaluation referenciada.
    """

    decision_id: TypedId
    grant_id: UUID
    evaluation_id: TypedId
    policy_id: TypedId
    proposer_organization_id: OrganizationId
    proposal_content: str
    proposal_evidence_references: tuple[str, ...]
    proposed_at: datetime
    reviewer_organization_id: OrganizationId
    status: str
    created_by: str
    record_owner_organization_id: OrganizationId
    review_decision: str | None = None
    review_content: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None

    def __post_init__(self) -> None:
        if self.decision_id.entity_type != SHARED_DECISION_ENTITY_TYPE:
            raise ValueError("decision_id deve ser do tipo shared_decision.")
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo evaluation.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo policy.")
        if not self.proposal_content.strip():
            raise ValueError("proposal_content e obrigatorio.")
        if self.status not in VALID_SHARED_DECISION_STATUSES:
            raise ValueError("status de SharedDecision invalido.")
        require_utc(self.proposed_at, field_name="proposed_at")
        if self.reviewed_at is not None:
            require_utc(self.reviewed_at, field_name="reviewed_at")
        if self.status == SHARED_DECISION_STATUS_PROPOSTA:
            if self.review_decision is not None or self.reviewed_at is not None:
                raise ValueError("SharedDecision em PROPOSTA nao possui revisao.")
        if self.status == SHARED_DECISION_STATUS_REVISADA:
            if self.review_decision not in VALID_SHARED_DECISION_REVIEW_DECISIONS:
                raise ValueError("review_decision invalida.")
            if self.review_content is None or not self.review_content.strip():
                raise ValueError("review_content e obrigatorio na revisao.")
            if self.reviewed_at is None:
                raise ValueError("reviewed_at e obrigatorio na revisao.")
            if self.reviewed_by is None or not self.reviewed_by.strip():
                raise ValueError("reviewed_by e obrigatorio na revisao.")
        for reference in self.proposal_evidence_references:
            if not reference.strip():
                raise ValueError("proposal_evidence_references nao aceita valor vazio.")


@dataclass(frozen=True, slots=True)
class SharedPolicyAccessLogEntry:
    """Um acesso consumado a uma Policy compartilhada, sob um grant bilateral.

    Registro append-only: cada leitura ou avaliacao produz uma linha nova, e
    nenhuma linha e reescrita. O `http_status_code` faz parte do registro porque
    a trilha precisa distinguir acesso concedido de acesso recusado -- e e a
    recusa repetida que denuncia varredura de dataset (ADR-0066, secao 3).

    `organization_id` e quem acessou (a beneficiaria do grant);
    `record_owner_organization_id` e a dona da Policy, para quem a trilha existe.
    """

    access_id: TypedId
    grant_id: UUID
    policy_id: TypedId
    organization_id: OrganizationId
    action: str
    http_status_code: int
    accessed_at: datetime
    record_owner_organization_id: OrganizationId
    subject_type: str | None = None
    subject_id: str | None = None

    def __post_init__(self) -> None:
        if self.access_id.entity_type != SHARED_POLICY_ACCESS_ENTITY_TYPE:
            raise ValueError("access_id deve ser do tipo shared_policy_access.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo policy.")
        if self.action not in VALID_SHARED_POLICY_ACCESS_ACTIONS:
            raise ValueError("action de SharedPolicyAccessLogEntry invalida.")
        if not 100 <= self.http_status_code <= 599:
            raise ValueError("http_status_code fora da faixa HTTP.")
        require_utc(self.accessed_at, field_name="accessed_at")
