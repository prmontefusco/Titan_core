"""Authorization profiles for Market Supply Intelligence (CUT F2).

This module prepares purpose/scope checks for future Market Supply access by
composing the existing Core `AuthorizationGrant` shape. It does not create grants,
persist profiles, expose APIs, resolve populations, or read cross-tenant data.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc

MARKET_SUPPLY_AGGREGATE_ASSESSMENT = "MARKET_SUPPLY_AGGREGATE_ASSESSMENT"
MARKET_SUPPLY_CANDIDATE_DISCLOSURE = "MARKET_SUPPLY_CANDIDATE_DISCLOSURE"

MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE = "MARKET_SUPPLY_AGGREGATE_V1"
MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE = "MARKET_SUPPLY_CANDIDATE_DISCLOSURE_V1"


class MarketSupplyAuthorizationResult(StrEnum):
    PERMITTED = "PERMITTED"
    DENIED = "DENIED"


class MarketSupplyAuthorizationReason(StrEnum):
    PERMITTED = "PERMITTED"
    MISSING_GRANT = "MISSING_GRANT"
    INACTIVE_GRANT = "INACTIVE_GRANT"
    REVOKED_GRANT = "REVOKED_GRANT"
    EXPIRED_OR_NOT_YET_VALID = "EXPIRED_OR_NOT_YET_VALID"
    OWNER_ORGANIZATION_MISMATCH = "OWNER_ORGANIZATION_MISMATCH"
    BENEFICIARY_ORGANIZATION_MISMATCH = "BENEFICIARY_ORGANIZATION_MISMATCH"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
    FIELD_SCOPE_MISMATCH = "FIELD_SCOPE_MISMATCH"


@dataclass(frozen=True, slots=True)
class MarketSupplyAuthorizationRequest:
    owner_organization_id: OrganizationId
    beneficiary_organization_id: OrganizationId
    policy_id: TypedId
    access_purpose: str
    field_scope_profile: str
    requested_at: datetime

    def __post_init__(self) -> None:
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ter entity_type 'policy'.")
        if not self.access_purpose.strip():
            raise ValueError("access_purpose deve ser texto nao vazio.")
        if not self.field_scope_profile.strip():
            raise ValueError("field_scope_profile deve ser texto nao vazio.")
        require_utc(self.requested_at, field_name="requested_at")


@dataclass(frozen=True, slots=True)
class MarketSupplyAuthorizationAssessment:
    result: MarketSupplyAuthorizationResult
    reason: MarketSupplyAuthorizationReason
    access_purpose: str
    field_scope_profile: str

    @property
    def permitted(self) -> bool:
        return self.result is MarketSupplyAuthorizationResult.PERMITTED


class MarketSupplyAuthorizationService:
    """Evaluates purpose-bound Market Supply grants without performing data access."""

    def assess_aggregate_access(
        self,
        *,
        request: MarketSupplyAuthorizationRequest,
        grant: AuthorizationGrant | None,
    ) -> MarketSupplyAuthorizationAssessment:
        return self._assess(
            request=request,
            grant=grant,
            expected_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            expected_field_scope=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        )

    def assess_candidate_disclosure(
        self,
        *,
        request: MarketSupplyAuthorizationRequest,
        grant: AuthorizationGrant | None,
    ) -> MarketSupplyAuthorizationAssessment:
        return self._assess(
            request=request,
            grant=grant,
            expected_purpose=MARKET_SUPPLY_CANDIDATE_DISCLOSURE,
            expected_field_scope=MARKET_SUPPLY_CANDIDATE_DISCLOSURE_FIELD_SCOPE,
        )

    def _assess(
        self,
        *,
        request: MarketSupplyAuthorizationRequest,
        grant: AuthorizationGrant | None,
        expected_purpose: str,
        expected_field_scope: str,
    ) -> MarketSupplyAuthorizationAssessment:
        if grant is None:
            return _denied(request, MarketSupplyAuthorizationReason.MISSING_GRANT)
        if grant.status != "ATIVO":
            return _denied(request, MarketSupplyAuthorizationReason.INACTIVE_GRANT)
        if grant.revoked_at is not None and grant.revoked_at <= request.requested_at:
            return _denied(request, MarketSupplyAuthorizationReason.REVOKED_GRANT)
        if not (grant.valid_from <= request.requested_at < grant.valid_until):
            return _denied(request, MarketSupplyAuthorizationReason.EXPIRED_OR_NOT_YET_VALID)
        if grant.owner_organization_id != request.owner_organization_id:
            return _denied(request, MarketSupplyAuthorizationReason.OWNER_ORGANIZATION_MISMATCH)
        if grant.beneficiary_organization_id != request.beneficiary_organization_id:
            return _denied(
                request,
                MarketSupplyAuthorizationReason.BENEFICIARY_ORGANIZATION_MISMATCH,
            )
        if grant.policy_id != request.policy_id:
            return _denied(request, MarketSupplyAuthorizationReason.POLICY_MISMATCH)
        if request.access_purpose != expected_purpose or grant.access_purpose != expected_purpose:
            return _denied(request, MarketSupplyAuthorizationReason.PURPOSE_MISMATCH)
        if (
            request.field_scope_profile != expected_field_scope
            or grant.field_scope_profile != expected_field_scope
        ):
            return _denied(request, MarketSupplyAuthorizationReason.FIELD_SCOPE_MISMATCH)
        return MarketSupplyAuthorizationAssessment(
            result=MarketSupplyAuthorizationResult.PERMITTED,
            reason=MarketSupplyAuthorizationReason.PERMITTED,
            access_purpose=request.access_purpose,
            field_scope_profile=request.field_scope_profile,
        )


def _denied(
    request: MarketSupplyAuthorizationRequest,
    reason: MarketSupplyAuthorizationReason,
) -> MarketSupplyAuthorizationAssessment:
    return MarketSupplyAuthorizationAssessment(
        result=MarketSupplyAuthorizationResult.DENIED,
        reason=reason,
        access_purpose=request.access_purpose,
        field_scope_profile=request.field_scope_profile,
    )
