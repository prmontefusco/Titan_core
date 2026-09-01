"""PostgreSQL integration for Market Supply workflow audit composition."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_domain import Organization
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.livestock_application.market_supply_audit import MarketSupplyRevocationState
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
    MarketSupplyAuthorizationRequest,
)
from packages.livestock_application.market_supply_population import (
    CandidatePopulationCriteria,
    CandidatePopulationResolver,
    CandidatePopulationSubject,
)
from packages.livestock_application.market_supply_privacy import (
    AggregationGeographicPrecision,
    AggregationPrivacyInput,
    AggregationPrivacyPolicy,
    AggregationQueryFingerprint,
)
from packages.livestock_application.market_supply_response import (
    MarketSupplyPublicResponseStatus,
)
from packages.livestock_application.market_supply_workflow import (
    MarketSupplyAggregateGateRequest,
    MarketSupplyAggregateGateWorkflow,
    MarketSupplyAuditRecordContext,
)
from packages.livestock_infrastructure.persistence.market_supply_query_audit_repository import (
    TransactionalMarketSupplyQueryAuditRepository,
)
from packages.shared_kernel import OrganizationId, TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL nao configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_market_supply_workflow_releases_only_after_durable_audit_append() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_market_supply_workflow_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                owner = Organization.create()
                buyer = Organization.create()
                for organization in (owner, buyer):
                    set_local_organization_context(connection, organization.organization_id)
                    OrganizationRepository(connection).add(organization)

                policy_id = _insert_policy(connection, owner.organization_id)
                policy_version_id = TypedId.new("policy_version")
                grant_id = _insert_grant(
                    connection,
                    owner_organization_id=owner.organization_id,
                    beneficiary_organization_id=buyer.organization_id,
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
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
                        "GRANT SELECT, INSERT "
                        "ON core_audit.market_supply_query_audit_records "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(
                    text(f"GRANT SELECT ON core_audit.authorization_grants TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, owner.organization_id)
                repository = TransactionalMarketSupplyQueryAuditRepository(connection)
                grant = AuthorizationGrant(
                    grant_id=grant_id,
                    owner_organization_id=owner.organization_id,
                    beneficiary_organization_id=buyer.organization_id,
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
                    access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                    field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
                    valid_from=NOW - timedelta(days=1),
                    valid_until=NOW + timedelta(days=30),
                    status="ATIVO",
                    created_at=NOW - timedelta(days=1),
                    created_by="market-supply-workflow-test",
                    record_owner_organization_id=owner.organization_id,
                )
                criteria = CandidatePopulationCriteria(
                    organization_id=owner.organization_id,
                    purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                    policy_id=policy_id,
                    policy_version=1,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                    required_tags=("ready",),
                )
                snapshot = CandidatePopulationResolver().resolve(
                    criteria=criteria,
                    subjects=tuple(
                        CandidatePopulationSubject(
                            subject_id=TypedId.new("animal"),
                            organization_id=owner.organization_id,
                            tags=("ready",),
                            known_at=NOW - timedelta(hours=1),
                        )
                        for _ in range(6)
                    ),
                    resolved_at=NOW,
                )
                query_fingerprint = AggregationQueryFingerprint(
                    requester_organization_id=buyer.organization_id,
                    beneficiary_organization_id=buyer.organization_id,
                    access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                    policy_context_digest=snapshot.criteria.policy_context_digest(),
                    filter_fingerprint="region=synthetic-ready",
                    result_subject_count=snapshot.included_count,
                    requested_at=NOW,
                )
                aggregate_payload = {
                    "ready_now": snapshot.included_count,
                    "conditioned": 0,
                    "indeterminate": 0,
                    "not_ready": 0,
                    "not_evaluated": 0,
                }
                semantic_request_digest = f"request:sha256:{uuid4().hex}"
                audit_context = MarketSupplyAuditRecordContext(
                    audit_id=TypedId.new("market_supply_query_audit"),
                    policy_version=1,
                    privacy_profile_id="market-supply-aggregate-integration",
                    authorization_context_digest=f"authorization:sha256:{uuid4().hex}",
                    candidate_population_digest=snapshot.snapshot_digest,
                    population_digest=snapshot.internal_universe_summary().population_digest,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                    requested_at=NOW,
                    revocation_state=MarketSupplyRevocationState.NOT_REVOKED,
                    correlation_id=TypedId.new("correlation"),
                    idempotency_reference=f"idempotency-key:{uuid4().hex}",
                    semantic_request_digest=semantic_request_digest,
                )

                result = MarketSupplyAggregateGateWorkflow(
                    audit_repository=repository,
                    grant_reader=TransactionalAuthorizationGrantRepository(connection),
                ).assess_aggregate_access(
                    MarketSupplyAggregateGateRequest(
                        audit_owner_organization_id=owner.organization_id,
                        authorization_request=MarketSupplyAuthorizationRequest(
                            owner_organization_id=owner.organization_id,
                            beneficiary_organization_id=buyer.organization_id,
                            policy_id=policy_id,
                            access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                            field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
                            requested_at=NOW,
                        ),
                        query_policy_id=policy_id,
                        query_fingerprint=query_fingerprint,
                        recorded_at=NOW,
                        grant=grant,
                        population_snapshot=snapshot,
                        privacy_input=AggregationPrivacyInput(
                            privacy_policy=AggregationPrivacyPolicy(
                                policy_version=1,
                                minimum_organizations=1,
                                minimum_properties=1,
                                minimum_subjects=1,
                                max_filter_count_without_review=3,
                                repeated_query_window=timedelta(minutes=5),
                            ),
                            organization_count=1,
                            property_count=1,
                            subject_count=snapshot.included_count,
                            geographic_precision=AggregationGeographicPrecision.REGION,
                            filter_count=1,
                            rare_attribute_filters=(),
                            current_query=query_fingerprint,
                        ),
                        aggregate_payload=aggregate_payload,
                        audit_record_context=audit_context,
                    ),
                )

                assert result.public_response.status is MarketSupplyPublicResponseStatus.RELEASED
                assert result.aggregate_result is not None
                assert result.aggregate_result.audit_record == result.audit_record
                assert result.aggregate_result.population_snapshot == snapshot
                assert result.aggregate_result.aggregate_payload == aggregate_payload

                persisted = repository.get(audit_context.audit_id)
                assert persisted == result.audit_record
                assert persisted is not None
                assert persisted.result_digest == result.audit_record.result_digest

                set_local_organization_context(connection, buyer.organization_id)
                assert repository.get(audit_context.audit_id) is None
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
                'Market Supply Workflow Test Policy',
                'Synthetic policy only for Market Supply workflow audit test.',
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
            "code": f"MARKET_SUPPLY_WORKFLOW_TEST_{uuid4().hex}",
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
    policy_version_id: TypedId,
) -> UUID:
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
                'market-supply-workflow-test',
                :owner_organization_id
            )
            """
        ),
        {
            "grant_id": grant_id,
            "owner_organization_id": owner_organization_id.value,
            "beneficiary_organization_id": beneficiary_organization_id.value,
            "policy_id": policy_id.value,
            "policy_version_id": policy_version_id.value,
            "access_purpose": MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            "field_scope_profile": MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
            "valid_from": NOW - timedelta(days=1),
            "valid_until": NOW + timedelta(days=30),
            "created_at": NOW - timedelta(days=1),
        },
    )
    return grant_id
