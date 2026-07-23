"""Contratos e invariantes universais do domínio Titan."""

from packages.core_domain.authentication import AuthenticatedPrincipal, PrincipalType
from packages.core_domain.authorization import (
    MembershipRoleAssignment,
    MembershipRoleRevocation,
    Permission,
    Role,
)
from packages.core_domain.corrections import ChangeKind, Correction, build_correction
from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
    KeyRecord,
    KeyState,
    SignatureStatus,
    ValidationResult,
)
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    aggregate_outcome,
    compute_conditions_digest,
    compute_evaluation_hash,
    compute_rule_inputs_hash,
)
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.core_domain.evidence import (
    Attachment,
    ConfidenceLevel,
    ConfidenceTier,
    Evidence,
    EvidenceRevocation,
    Source,
    SourceType,
    ValidityPeriod,
    VerificationOutcome,
    VerificationRecord,
    compute_content_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.memberships import Membership, MembershipStatus
from packages.core_domain.nonconformity import (
    NonConformity,
    NonConformityOrigin,
    NonConformityStatus,
    NonConformityTransition,
)
from packages.core_domain.organization_context import (
    ExternalIdentity,
    ExternalIdentityStatus,
    OrganizationContext,
)
from packages.core_domain.organizations import Organization
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.projections import (
    ReferenceRole,
    ReferencingKind,
    ReverseReference,
    compute_projection_digest,
)
from packages.core_domain.provenance import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceTrace,
)
from packages.core_domain.relations import UniversalRelation
from packages.core_domain.rule import (
    ComparisonOperator,
    ConditionOutcome,
    Rule,
    RuleCondition,
    SeverityLevel,
)
from packages.core_domain.users import User

__all__ = [
    "CanonicalPayload",
    "ChangeKind",
    "Correction",
    "AuthenticatedPrincipal",
    "Attachment",
    "DomainEvent",
    "ProvenanceNodeType",
    "ProvenanceNode",
    "ProvenanceEdge",
    "ProvenanceTrace",
    "Policy",
    "PolicyStatus",
    "Rule",
    "RuleCondition",
    "ComparisonOperator",
    "ConditionOutcome",
    "RuleResult",
    "RuleResultStatus",
    "compute_conditions_digest",
    "compute_rule_inputs_hash",
    "SeverityLevel",
    "Evaluation",
    "EvaluationOutcome",
    "aggregate_outcome",
    "compute_evaluation_hash",
    "Decision",
    "DecisionReason",
    "DecisionReasonCode",
    "DecisionResult",
    "compute_decision_hash",
    "UniversalRelation",
    "ReverseReference",
    "ReferencingKind",
    "ReferenceRole",
    "compute_projection_digest",
    "NonConformity",
    "NonConformityOrigin",
    "NonConformityStatus",
    "NonConformityTransition",
    "Fact",
    "FactSnapshot",
    "CryptographicProfile",
    "CryptographicSignature",
    "KeyIdentifier",
    "KeyRecord",
    "KeyState",
    "SignatureStatus",
    "ValidationResult",
    "Evidence",
    "EvidenceRevocation",
    "ValidityPeriod",
    "VerificationOutcome",
    "VerificationRecord",
    "ConfidenceLevel",
    "ConfidenceTier",
    "Source",
    "SourceType",
    "compute_content_hash",
    "ExternalIdentity",
    "ExternalIdentityStatus",
    "Membership",
    "MembershipRoleAssignment",
    "MembershipRoleRevocation",
    "MembershipStatus",
    "Organization",
    "OrganizationContext",
    "Permission",
    "PrincipalType",
    "Role",
    "User",
    "build_correction",
]
