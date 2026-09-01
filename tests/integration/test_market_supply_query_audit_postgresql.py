"""PostgreSQL/RLS tests for Market Supply query audit persistence."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.livestock_application.market_supply_audit import (
    MarketSupplyAggregateQueryAuditPlanner,
    MarketSupplyAggregateQueryAuditRequest,
    MarketSupplyQueryAuditRecord,
    MarketSupplyRevocationState,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationAssessment,
    MarketSupplyAuthorizationReason,
    MarketSupplyAuthorizationResult,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationPrivacyAssessment,
    AggregationPrivacyDecision,
    AggregationPrivacyReason,
    AggregationQueryFingerprint,
    DisclosureDecision,
    DisclosureDecisionState,
)
from packages.livestock_infrastructure.persistence.market_supply_query_audit_repository import (
    TransactionalMarketSupplyQueryAuditRepository,
)
from packages.shared_kernel import OrganizationId, TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_market_supply_query_audit_is_inserted_append_only_and_rls_isolated() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_market_supply_audit_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                owner = Organization.create()
                other = Organization.create()
                for organization in (owner, other):
                    set_local_organization_context(connection, organization.organization_id)
                    OrganizationRepository(connection).add(organization)
                policy_id = _insert_policy(connection, owner.organization_id)
                grant_id = _insert_grant(
                    connection,
                    owner_organization_id=owner.organization_id,
                    beneficiary_organization_id=other.organization_id,
                    policy_id=policy_id,
                )
                record = _audit_record(
                    owner_organization_id=owner.organization_id,
                    beneficiary_organization_id=other.organization_id,
                    policy_id=policy_id,
                    grant_id=grant_id,
                )

                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(
                    text(
                        "GRANT SELECT, INSERT, UPDATE, DELETE "
                        "ON core_audit.market_supply_query_audit_records "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, owner.organization_id)
                repository = TransactionalMarketSupplyQueryAuditRepository(connection)
                repository.append(record)
                assert repository.get(record.audit_id) == record

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        repository.append(record)

                set_local_organization_context(connection, other.organization_id)
                assert repository.get(record.audit_id) is None
                assert (
                    repository.find_related_query_fingerprints(
                        requester_organization_id=record.requester_organization_id,
                        beneficiary_organization_id=record.beneficiary_organization_id,
                        access_purpose=record.access_purpose,
                        policy_context_digest=record.query_fingerprint.policy_context_digest,
                    )
                    == ()
                )

                set_local_organization_context(connection, owner.organization_id)
                updated = connection.execute(
                    text(
                        """
                        UPDATE core_audit.market_supply_query_audit_records
                        SET result_digest = 'result:sha256:tampered'
                        WHERE audit_id = :audit_id
                        """
                    ),
                    {"audit_id": record.audit_id.value},
                )
                assert updated.rowcount == 0

                deleted = connection.execute(
                    text(
                        """
                        DELETE FROM core_audit.market_supply_query_audit_records
                        WHERE audit_id = :audit_id
                        """
                    ),
                    {"audit_id": record.audit_id.value},
                )
                assert deleted.rowcount == 0
                assert repository.get(record.audit_id) == record
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _insert_policy(connection: object, organization_id: OrganizationId) -> TypedId:
    policy_id = TypedId.new("policy")
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.policies (
                policy_id,
                record_owner_organization_id,
                code,
                name,
                description,
                version,
                status,
                valid_from,
                valid_to,
                created_at,
                published_at
            ) VALUES (
                :policy_id,
                :organization_id,
                :code,
                'Market Supply Test Policy',
                'Synthetic policy only for Market Supply audit persistence test.',
                1,
                'PUBLISHED',
                :valid_from,
                NULL,
                :created_at,
                :published_at
            )
            """
        ),
        {
            "policy_id": policy_id.value,
            "organization_id": organization_id.value,
            "code": f"MARKET_SUPPLY_TEST_{uuid4().hex}",
            "valid_from": NOW,
            "created_at": NOW,
            "published_at": NOW,
        },
    )
    return policy_id


def _insert_grant(
    connection: object,
    *,
    owner_organization_id: OrganizationId,
    beneficiary_organization_id: OrganizationId,
    policy_id: TypedId,
) -> object:
    grant_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.authorization_grants (
                grant_id,
                owner_organization_id,
                beneficiary_organization_id,
                policy_id,
                policy_version_id,
                access_purpose,
                field_scope_profile,
                valid_from,
                valid_until,
                status,
                created_at,
                created_by,
                record_owner_organization_id
            ) VALUES (
                :grant_id,
                :owner_organization_id,
                :beneficiary_organization_id,
                :policy_id,
                :policy_version_id,
                :access_purpose,
                :field_scope_profile,
                :valid_from,
                :valid_until,
                'ATIVO',
                :created_at,
                'market-supply-test',
                :owner_organization_id
            )
            """
        ),
        {
            "grant_id": grant_id,
            "owner_organization_id": owner_organization_id.value,
            "beneficiary_organization_id": beneficiary_organization_id.value,
            "policy_id": policy_id.value,
            "policy_version_id": uuid4(),
            "access_purpose": MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            "field_scope_profile": MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
            "valid_from": NOW,
            "valid_until": datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
            "created_at": NOW,
        },
    )
    return grant_id


def _audit_record(
    *,
    owner_organization_id: OrganizationId,
    beneficiary_organization_id: OrganizationId,
    policy_id: TypedId,
    grant_id: object,
) -> MarketSupplyQueryAuditRecord:
    query = AggregationQueryFingerprint(
        requester_organization_id=owner_organization_id,
        beneficiary_organization_id=beneficiary_organization_id,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_context_digest="population:sha256:integration",
        filter_fingerprint="region=macro-a",
        result_subject_count=42,
        requested_at=NOW,
    )
    request = MarketSupplyAggregateQueryAuditRequest(
        audit_owner_organization_id=owner_organization_id,
        requester_organization_id=owner_organization_id,
        beneficiary_organization_id=beneficiary_organization_id,
        policy_id=policy_id,
        access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        query_fingerprint=query,
        recorded_at=NOW,
        authorization=MarketSupplyAuthorizationAssessment(
            result=MarketSupplyAuthorizationResult.PERMITTED,
            reason=MarketSupplyAuthorizationReason.PERMITTED,
            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
        ),
        privacy=AggregationPrivacyAssessment(
            decision=AggregationPrivacyDecision.PERMITTED,
            reasons=(AggregationPrivacyReason.PERMITTED,),
            policy_version=1,
        ),
        grant_id=grant_id,  # type: ignore[arg-type]
    )
    envelope = MarketSupplyAggregateQueryAuditPlanner().plan(request)
    return MarketSupplyQueryAuditRecord.from_envelope(
        audit_id=TypedId.new("market_supply_query_audit"),
        envelope=envelope,
        policy_version=1,
        privacy_profile_id="market-supply-aggregate-test",
        authorization_context_digest="authorization:sha256:integration",
        candidate_population_digest="population:sha256:integration",
        population_digest="population:sha256:internal",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        requested_at=NOW,
        disclosure_decision=DisclosureDecision(
            state=DisclosureDecisionState.ALLOW,
            reason_codes=("PERMITTED",),
            privacy_policy_version=1,
            query_fingerprint=query,
            candidate_population_digest="population:sha256:integration",
            evaluated_at=NOW,
        ),
        result_digest="result:sha256:integration",
        revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
        correlation_id=TypedId.new("correlation"),
        idempotency_reference="idempotency-key:integration",
        semantic_request_digest="request:sha256:integration",
    )
