"""PostgreSQL/RLS tests for AI Explanation audit persistence."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.livestock_application.market_optionality import (
    MarketOptionAssessmentService,
    MarketOptionExplanationAuditRecord,
    MarketOptionExplanationPipelineService,
)
from packages.livestock_infrastructure.persistence.ai_explanation_audit_repository import (
    TransactionalAIExplanationAuditRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_market_optionality import (
    PURPOSE,
    _ai_run_context,
    _context_from_artifacts,
)
from tests.livestock_application.test_market_readiness import _artifacts

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_ai_explanation_audit_is_inserted_append_only_and_rls_isolated() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_ai_explanation_audit_{uuid4().hex}"
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
                record = _audit_record(
                    owner_organization_id=owner.organization_id,
                    policy_id=policy_id,
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
                        "ON core_audit.ai_explanation_audit_records "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, owner.organization_id)
                repository = TransactionalAIExplanationAuditRepository(connection)
                repository.append(record)
                assert repository.get(record.audit_id) == record

                with pytest.raises(IntegrityError):
                    with connection.begin_nested():
                        repository.append(record)

                assert repository.find_by_correlation_id(
                    record_owner_organization_id=owner.organization_id,
                    correlation_id=record.correlation_id,
                ) == (record,)
                assert record.idempotency_reference is not None
                assert repository.find_by_idempotency_reference(
                    record_owner_organization_id=owner.organization_id,
                    idempotency_reference=record.idempotency_reference,
                ) == (record,)

                set_local_organization_context(connection, other.organization_id)
                assert repository.get(record.audit_id) is None
                assert (
                    repository.find_by_correlation_id(
                        record_owner_organization_id=owner.organization_id,
                        correlation_id=record.correlation_id,
                    )
                    == ()
                )
                assert (
                    repository.find_by_idempotency_reference(
                        record_owner_organization_id=owner.organization_id,
                        idempotency_reference=record.idempotency_reference,
                    )
                    == ()
                )

                set_local_organization_context(connection, owner.organization_id)
                updated = connection.execute(
                    text(
                        """
                        UPDATE core_audit.ai_explanation_audit_records
                        SET released_output_digest = :tampered
                        WHERE audit_id = :audit_id
                        """
                    ),
                    {"audit_id": record.audit_id.value, "tampered": "a" * 64},
                )
                assert updated.rowcount == 0

                deleted = connection.execute(
                    text(
                        """
                        DELETE FROM core_audit.ai_explanation_audit_records
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
                'AI Explanation Audit Test Policy',
                'Synthetic policy only for AI Explanation audit persistence test.',
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
            "code": f"AI_EXPLANATION_AUDIT_TEST_{uuid4().hex}",
            "valid_from": NOW,
            "created_at": NOW,
            "published_at": NOW,
        },
    )
    return policy_id


def _audit_record(
    *,
    owner_organization_id: OrganizationId,
    policy_id: TypedId,
) -> MarketOptionExplanationAuditRecord:
    decision, evaluation, policy = _artifacts(
        purpose=PURPOSE,
        organization_id=owner_organization_id,
        policy_id=policy_id,
    )
    assessment = MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )
    result = MarketOptionExplanationPipelineService().explain(
        assessment=assessment,
        run_context=_ai_run_context(owner_organization_id, idempotency_key="idem-secret"),
    )
    return MarketOptionExplanationAuditRecord.from_result(
        audit_id=TypedId.new("ai_explanation_audit"),
        result=result,
        requested_at=NOW,
        evaluated_at=NOW + timedelta(seconds=1),
        correlation_id=TypedId.new("correlation"),
    )
