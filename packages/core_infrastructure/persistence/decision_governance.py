"""Persistencia PostgreSQL para governanca de decisao (ADR-0053/ADR-0054)."""

import json
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Connection,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from packages.core_domain.decision import DecisionReason, DecisionResult
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import (
    ContestationRecord,
    DecisionAuthorityProfile,
    DecisionOverride,
    DecisionProposal,
    DecisionReview,
    GovernanceStatus,
    ReviewConclusion,
)
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_infrastructure.persistence.events import CORE_AUDIT_SCHEMA
from packages.core_infrastructure.persistence.organizations import organization_metadata
from packages.shared_kernel import OrganizationId, TypedId

decision_authority_profiles_table = Table(
    "decision_authority_profiles",
    organization_metadata,
    Column("authority_profile_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("principal_reference", JSONB, nullable=False),
    Column("role_name", String(255), nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("emission_method", String(50), nullable=False),
    Column("approvals_required", Integer, nullable=False),
    Column("max_delegated_severity", String(50), nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("valid_from", DateTime(timezone=True), nullable=True),
    Column("valid_to", DateTime(timezone=True), nullable=True),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_authority_profiles_organization",
    ),
    UniqueConstraint(
        "authority_profile_id",
        "record_owner_organization_id",
        name="uq_decision_authority_profiles_id_org",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

decision_proposals_table = Table(
    "decision_proposals",
    organization_metadata,
    Column("proposal_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_id", PG_UUID(as_uuid=True), nullable=False),
    Column("evaluation_hash", String(64), nullable=False),
    Column("proposed_result", String(50), nullable=False),
    Column("proposed_reasons", JSONB, nullable=False),
    Column("purpose", String(255), nullable=False),
    Column("justification_required", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_proposals_organization",
    ),
    ForeignKeyConstraint(
        ["evaluation_id"],
        ["core_audit.evaluations.evaluation_id"],
        name="fk_decision_proposals_evaluation",
    ),
    CheckConstraint(
        "jsonb_array_length(proposed_reasons) > 0",
        name="ck_decision_proposals_reasons_not_empty",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

decision_reviews_table = Table(
    "decision_reviews",
    organization_metadata,
    Column("review_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("proposal_id", PG_UUID(as_uuid=True), nullable=False),
    Column("reviewer_reference", JSONB, nullable=False),
    Column("reviewer_authority_id", PG_UUID(as_uuid=True), nullable=False),
    Column("conclusion", String(50), nullable=False),
    Column("reasoning", String, nullable=False),
    Column("reviewed_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_reviews_organization",
    ),
    ForeignKeyConstraint(
        ["proposal_id"],
        ["core_audit.decision_proposals.proposal_id"],
        name="fk_decision_reviews_proposal",
    ),
    ForeignKeyConstraint(
        ["reviewer_authority_id", "record_owner_organization_id"],
        [
            "core_audit.decision_authority_profiles.authority_profile_id",
            "core_audit.decision_authority_profiles.record_owner_organization_id",
        ],
        name="fk_decision_reviews_authority_profile",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

decision_overrides_table = Table(
    "decision_overrides",
    organization_metadata,
    Column("override_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("original_decision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("authority_profile_id", PG_UUID(as_uuid=True), nullable=False),
    Column("new_result", String(50), nullable=False),
    Column("mandatory_reason", String, nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_overrides_organization",
    ),
    ForeignKeyConstraint(
        ["original_decision_id"],
        ["core_audit.decisions.decision_id"],
        name="fk_decision_overrides_decision",
    ),
    ForeignKeyConstraint(
        ["authority_profile_id", "record_owner_organization_id"],
        [
            "core_audit.decision_authority_profiles.authority_profile_id",
            "core_audit.decision_authority_profiles.record_owner_organization_id",
        ],
        name="fk_decision_overrides_authority_profile",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)

decision_contestations_table = Table(
    "decision_contestations",
    organization_metadata,
    Column("contestation_id", PG_UUID(as_uuid=True), primary_key=True),
    Column("record_owner_organization_id", PG_UUID(as_uuid=True), nullable=False),
    Column("decision_id", PG_UUID(as_uuid=True), nullable=False),
    Column("contested_by", JSONB, nullable=False),
    Column("grounds_description", String, nullable=False),
    Column("status", String(50), nullable=False),
    Column("filed_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True), nullable=True),
    Column("resolution_notes", String, nullable=False, server_default=""),
    ForeignKeyConstraint(
        ["record_owner_organization_id"],
        ["core_identity.organizations.organization_id"],
        name="fk_decision_contestations_organization",
    ),
    ForeignKeyConstraint(
        ["decision_id"],
        ["core_audit.decisions.decision_id"],
        name="fk_decision_contestations_decision",
    ),
    schema=CORE_AUDIT_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_audit",
)


def _loaded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class TransactionalDecisionAuthorityProfileRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError(
                "TransactionalDecisionAuthorityProfileRepository exige transacao ativa."
            )

    def save(self, profile: DecisionAuthorityProfile) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_authority_profiles (
                    authority_profile_id,
                    record_owner_organization_id,
                    principal_reference,
                    role_name,
                    purpose,
                    emission_method,
                    approvals_required,
                    max_delegated_severity,
                    is_active,
                    valid_from,
                    valid_to
                ) VALUES (
                    :authority_profile_id,
                    :org_id,
                    :principal_reference,
                    :role_name,
                    :purpose,
                    :emission_method,
                    :approvals_required,
                    :max_delegated_severity,
                    :is_active,
                    :valid_from,
                    :valid_to
                )
                """
            ),
            {
                "authority_profile_id": profile.authority_id.value,
                "org_id": profile.organization_id.value,
                "principal_reference": json.dumps(reference_to_dict(profile.principal_reference)),
                "role_name": profile.role_name,
                "purpose": profile.purpose,
                "emission_method": profile.emission_method.value,
                "approvals_required": profile.approvals_required,
                "max_delegated_severity": profile.max_delegated_severity,
                "is_active": profile.is_active,
                "valid_from": profile.valid_from,
                "valid_to": profile.valid_to,
            },
        )

    def get_by_id(self, authority_id: TypedId) -> DecisionAuthorityProfile | None:
        row = self.connection.execute(
            text(
                """
                SELECT authority_profile_id,
                       record_owner_organization_id,
                       principal_reference,
                       role_name,
                       purpose,
                       emission_method,
                       approvals_required,
                       max_delegated_severity,
                       is_active,
                       valid_from,
                       valid_to
                  FROM core_audit.decision_authority_profiles
                 WHERE authority_profile_id = :authority_id
                """
            ),
            {"authority_id": authority_id.value},
        ).first()
        if row is None:
            return None
        valid_from = (
            row.valid_from.replace(tzinfo=UTC)
            if row.valid_from is not None and row.valid_from.tzinfo is None
            else row.valid_from
        )
        valid_to = (
            row.valid_to.replace(tzinfo=UTC)
            if row.valid_to is not None and row.valid_to.tzinfo is None
            else row.valid_to
        )
        principal_reference = reference_from_dict(_loaded(row.principal_reference))
        if principal_reference is None:
            raise ValueError("principal_reference persistida da autoridade deve ser valida.")
        return DecisionAuthorityProfile(
            authority_id=TypedId(entity_type="authority_profile", value=row.authority_profile_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            principal_reference=principal_reference,
            role_name=row.role_name,
            purpose=row.purpose,
            emission_method=DecisionEmissionMethod(row.emission_method),
            approvals_required=row.approvals_required,
            max_delegated_severity=row.max_delegated_severity,
            is_active=row.is_active,
            valid_from=valid_from,
            valid_to=valid_to,
        )


@dataclass(frozen=True, slots=True)
class TransactionalDecisionGovernanceRepository:
    connection: Connection

    def __post_init__(self) -> None:
        if not isinstance(self.connection, Connection) or not self.connection.in_transaction():
            raise RuntimeError("TransactionalDecisionGovernanceRepository exige transacao ativa.")

    def save_proposal(self, proposal: DecisionProposal) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_proposals (
                    proposal_id,
                    record_owner_organization_id,
                    evaluation_id,
                    evaluation_hash,
                    proposed_result,
                    proposed_reasons,
                    purpose,
                    justification_required,
                    created_at
                ) VALUES (
                    :proposal_id,
                    :org_id,
                    :evaluation_id,
                    :evaluation_hash,
                    :proposed_result,
                    :proposed_reasons,
                    :purpose,
                    :justification_required,
                    :created_at
                )
                """
            ),
            {
                "proposal_id": proposal.proposal_id.value,
                "org_id": proposal.organization_id.value,
                "evaluation_id": proposal.evaluation_id.value,
                "evaluation_hash": proposal.evaluation_hash,
                "proposed_result": proposal.proposed_result.value,
                "proposed_reasons": json.dumps([r.to_dict() for r in proposal.proposed_reasons]),
                "purpose": proposal.purpose,
                "justification_required": proposal.justification_required,
                "created_at": proposal.created_at,
            },
        )

    def get_proposal(self, proposal_id: TypedId) -> DecisionProposal | None:
        row = self.connection.execute(
            text(
                """
                SELECT proposal_id,
                       record_owner_organization_id,
                       evaluation_id,
                       evaluation_hash,
                       proposed_result,
                       proposed_reasons,
                       purpose,
                       justification_required,
                       created_at
                  FROM core_audit.decision_proposals
                 WHERE proposal_id = :proposal_id
                """
            ),
            {"proposal_id": proposal_id.value},
        ).first()
        if row is None:
            return None
        created_at = (
            row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        )
        return DecisionProposal(
            proposal_id=TypedId(entity_type="decision_proposal", value=row.proposal_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            evaluation_id=TypedId(entity_type="evaluation", value=row.evaluation_id),
            evaluation_hash=row.evaluation_hash,
            proposed_result=DecisionResult(row.proposed_result),
            proposed_reasons=tuple(
                DecisionReason.from_dict(item) for item in _loaded(row.proposed_reasons)
            ),
            purpose=row.purpose,
            justification_required=row.justification_required,
            created_at=created_at,
        )

    def latest_proposal_for_evaluation(
        self,
        organization_id: OrganizationId,
        evaluation_id: TypedId,
        purpose: str,
    ) -> DecisionProposal | None:
        row = self.connection.execute(
            text(
                """
                SELECT proposal_id,
                       record_owner_organization_id,
                       evaluation_id,
                       evaluation_hash,
                       proposed_result,
                       proposed_reasons,
                       purpose,
                       justification_required,
                       created_at
                  FROM core_audit.decision_proposals
                 WHERE record_owner_organization_id = :org_id
                   AND evaluation_id = :evaluation_id
                   AND purpose = :purpose
                 ORDER BY created_at DESC, proposal_id DESC
                 LIMIT 1
                """
            ),
            {
                "org_id": organization_id.value,
                "evaluation_id": evaluation_id.value,
                "purpose": purpose,
            },
        ).first()
        if row is None:
            return None
        created_at = (
            row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at
        )
        return DecisionProposal(
            proposal_id=TypedId(entity_type="decision_proposal", value=row.proposal_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            evaluation_id=TypedId(entity_type="evaluation", value=row.evaluation_id),
            evaluation_hash=row.evaluation_hash,
            proposed_result=DecisionResult(row.proposed_result),
            proposed_reasons=tuple(
                DecisionReason.from_dict(item) for item in _loaded(row.proposed_reasons)
            ),
            purpose=row.purpose,
            justification_required=row.justification_required,
            created_at=created_at,
        )

    def save_review(self, review: DecisionReview) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_reviews (
                    review_id,
                    record_owner_organization_id,
                    proposal_id,
                    reviewer_reference,
                    reviewer_authority_id,
                    conclusion,
                    reasoning,
                    reviewed_at
                ) VALUES (
                    :review_id,
                    :org_id,
                    :proposal_id,
                    :reviewer_reference,
                    :reviewer_authority_id,
                    :conclusion,
                    :reasoning,
                    :reviewed_at
                )
                """
            ),
            {
                "review_id": review.review_id.value,
                "org_id": review.organization_id.value,
                "proposal_id": review.proposal_id.value,
                "reviewer_reference": json.dumps(reference_to_dict(review.reviewer_reference)),
                "reviewer_authority_id": review.reviewer_authority_id.value,
                "conclusion": review.conclusion.value,
                "reasoning": review.reasoning,
                "reviewed_at": review.reviewed_at,
            },
        )

    def get_review(self, review_id: TypedId) -> DecisionReview | None:
        row = self.connection.execute(
            text(
                """
                SELECT review_id,
                       record_owner_organization_id,
                       proposal_id,
                       reviewer_reference,
                       reviewer_authority_id,
                       conclusion,
                       reasoning,
                       reviewed_at
                  FROM core_audit.decision_reviews
                 WHERE review_id = :review_id
                """
            ),
            {"review_id": review_id.value},
        ).first()
        if row is None:
            return None
        reviewed_at = (
            row.reviewed_at.replace(tzinfo=UTC)
            if row.reviewed_at.tzinfo is None
            else row.reviewed_at
        )
        reviewer_reference = reference_from_dict(_loaded(row.reviewer_reference))
        if reviewer_reference is None:
            raise ValueError("reviewer_reference persistida da review deve ser valida.")
        return DecisionReview(
            review_id=TypedId(entity_type="decision_review", value=row.review_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            proposal_id=TypedId(entity_type="decision_proposal", value=row.proposal_id),
            reviewer_reference=reviewer_reference,
            reviewer_authority_id=TypedId(
                entity_type="authority_profile", value=row.reviewer_authority_id
            ),
            conclusion=ReviewConclusion(row.conclusion),
            reasoning=row.reasoning,
            reviewed_at=reviewed_at,
        )

    def list_reviews_by_proposal(self, proposal_id: TypedId) -> list[DecisionReview]:
        rows = self.connection.execute(
            text(
                """
                SELECT review_id,
                       record_owner_organization_id,
                       proposal_id,
                       reviewer_reference,
                       reviewer_authority_id,
                       conclusion,
                       reasoning,
                       reviewed_at
                  FROM core_audit.decision_reviews
                 WHERE proposal_id = :proposal_id
                 ORDER BY reviewed_at ASC, review_id ASC
                """
            ),
            {"proposal_id": proposal_id.value},
        ).fetchall()
        reviews: list[DecisionReview] = []
        for row in rows:
            reviewed_at = (
                row.reviewed_at.replace(tzinfo=UTC)
                if row.reviewed_at.tzinfo is None
                else row.reviewed_at
            )
            reviewer_reference = reference_from_dict(_loaded(row.reviewer_reference))
            if reviewer_reference is None:
                raise ValueError("reviewer_reference persistida da review deve ser valida.")
            reviews.append(
                DecisionReview(
                    review_id=TypedId(entity_type="decision_review", value=row.review_id),
                    organization_id=OrganizationId(row.record_owner_organization_id),
                    proposal_id=TypedId(entity_type="decision_proposal", value=row.proposal_id),
                    reviewer_reference=reviewer_reference,
                    reviewer_authority_id=TypedId(
                        entity_type="authority_profile", value=row.reviewer_authority_id
                    ),
                    conclusion=ReviewConclusion(row.conclusion),
                    reasoning=row.reasoning,
                    reviewed_at=reviewed_at,
                )
            )
        return reviews

    def save_override(self, override: DecisionOverride) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_overrides (
                    override_id,
                    record_owner_organization_id,
                    original_decision_id,
                    authority_profile_id,
                    new_result,
                    mandatory_reason,
                    applied_at
                ) VALUES (
                    :override_id,
                    :org_id,
                    :original_decision_id,
                    :authority_profile_id,
                    :new_result,
                    :mandatory_reason,
                    :applied_at
                )
                """
            ),
            {
                "override_id": override.override_id.value,
                "org_id": override.organization_id.value,
                "original_decision_id": override.original_decision_id.value,
                "authority_profile_id": override.authority_profile.authority_id.value,
                "new_result": override.new_result.value,
                "mandatory_reason": override.mandatory_reason,
                "applied_at": override.applied_at,
            },
        )

    def get_override(self, override_id: TypedId) -> DecisionOverride | None:
        row = self.connection.execute(
            text(
                """
                SELECT override_id,
                       record_owner_organization_id,
                       original_decision_id,
                       authority_profile_id,
                       new_result,
                       mandatory_reason,
                       applied_at
                  FROM core_audit.decision_overrides
                 WHERE override_id = :override_id
                """
            ),
            {"override_id": override_id.value},
        ).first()
        if row is None:
            return None
        authority = TransactionalDecisionAuthorityProfileRepository(self.connection).get_by_id(
            TypedId(entity_type="authority_profile", value=row.authority_profile_id)
        )
        if authority is None:
            raise ValueError("authority_profile persistida do override deve existir.")
        applied_at = (
            row.applied_at.replace(tzinfo=UTC) if row.applied_at.tzinfo is None else row.applied_at
        )
        return DecisionOverride(
            override_id=TypedId(entity_type="decision_override", value=row.override_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            original_decision_id=TypedId(entity_type="decision", value=row.original_decision_id),
            authority_profile=authority,
            new_result=DecisionResult(row.new_result),
            mandatory_reason=row.mandatory_reason,
            applied_at=applied_at,
        )

    def save_contestation(self, contestation: ContestationRecord) -> None:
        self.connection.execute(
            text(
                """
                INSERT INTO core_audit.decision_contestations (
                    contestation_id,
                    record_owner_organization_id,
                    decision_id,
                    contested_by,
                    grounds_description,
                    status,
                    filed_at,
                    resolved_at,
                    resolution_notes
                ) VALUES (
                    :contestation_id,
                    :org_id,
                    :decision_id,
                    :contested_by,
                    :grounds_description,
                    :status,
                    :filed_at,
                    :resolved_at,
                    :resolution_notes
                )
                """
            ),
            {
                "contestation_id": contestation.contestation_id.value,
                "org_id": contestation.organization_id.value,
                "decision_id": contestation.decision_id.value,
                "contested_by": json.dumps(reference_to_dict(contestation.contested_by)),
                "grounds_description": contestation.grounds_description,
                "status": contestation.status.value,
                "filed_at": contestation.filed_at,
                "resolved_at": contestation.resolved_at,
                "resolution_notes": contestation.resolution_notes,
            },
        )

    def get_contestation(self, contestation_id: TypedId) -> ContestationRecord | None:
        row = self.connection.execute(
            text(
                """
                SELECT contestation_id,
                       record_owner_organization_id,
                       decision_id,
                       contested_by,
                       grounds_description,
                       status,
                       filed_at,
                       resolved_at,
                       resolution_notes
                  FROM core_audit.decision_contestations
                 WHERE contestation_id = :contestation_id
                """
            ),
            {"contestation_id": contestation_id.value},
        ).first()
        if row is None:
            return None
        contested_by = reference_from_dict(_loaded(row.contested_by))
        if contested_by is None:
            raise ValueError("contested_by persistida da contestacao deve ser valida.")
        filed_at = row.filed_at.replace(tzinfo=UTC) if row.filed_at.tzinfo is None else row.filed_at
        resolved_at = None
        if row.resolved_at is not None:
            resolved_at = (
                row.resolved_at.replace(tzinfo=UTC)
                if row.resolved_at.tzinfo is None
                else row.resolved_at
            )
        return ContestationRecord(
            contestation_id=TypedId(entity_type="contestation", value=row.contestation_id),
            organization_id=OrganizationId(row.record_owner_organization_id),
            decision_id=TypedId(entity_type="decision", value=row.decision_id),
            contested_by=contested_by,
            grounds_description=row.grounds_description,
            status=GovernanceStatus(row.status),
            filed_at=filed_at,
            resolved_at=resolved_at,
            resolution_notes=row.resolution_notes,
        )
