"""End-to-end synthetic AI Explanation pipeline over PostgreSQL audit storage.

The roteiro composes a synthetic `MarketOptionAssessment`, the Gemini adapter
behind a stub transport, the deterministic guard and the transactional audit
repository. It proves that no AI text is released before durable owner-scoped
audit, and that provider or audit failure keeps the canonical fallback.
"""

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.livestock_application.market_optionality import (
    MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_TEXT,
    MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
    MarketOptionAssessment,
    MarketOptionAssessmentService,
    MarketOptionExplanationAuditRecordContext,
    MarketOptionExplanationPipelineService,
    MarketOptionExplanationProviderPayload,
    MarketOptionExplanationReleaseDisposition,
    MarketOptionExplanationRunContext,
    MarketOptionExplanationViolation,
)
from packages.livestock_infrastructure.ai_explanation_provider import (
    AIProviderHttpResponse,
    GeminiMarketOptionExplanationTextProvider,
)
from packages.livestock_infrastructure.persistence.ai_explanation_audit_repository import (
    TransactionalAIExplanationAuditRepository,
)
from packages.shared_kernel import OrganizationId, TypedId
from tests.livestock_application.test_market_optionality import (
    PURPOSE,
    _context_from_artifacts,
)
from tests.livestock_application.test_market_readiness import _artifacts

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
MODEL_NAME = "models/synthetic-explanation-model"
RELEASABLE_TEXT = "Resumo canônico sintético do estado de optionality."
PROVIDER_ERROR_TEXT = "provider stack trace with diagnostics"


@dataclass(slots=True)
class StubGeminiTransport:
    """Stub Gemini transport; the pipeline never reaches the network in tests."""

    calls: list[dict[str, Any]]
    status: int = 200
    text: str = RELEASABLE_TEXT

    def post_json(
        self,
        *,
        url: str,
        api_key: str,
        body: dict[str, Any],
        timeout_seconds: int,
    ) -> AIProviderHttpResponse:
        self.calls.append({"url": url, "body": body})
        if self.status != 200:
            return AIProviderHttpResponse(
                status=self.status,
                body={"error": {"code": self.status, "message": PROVIDER_ERROR_TEXT}},
            )
        return AIProviderHttpResponse(
            status=200,
            body={"candidates": [{"content": {"parts": [{"text": self.text}]}}]},
        )


class RecordingTextProvider:
    """Wraps the real adapter to capture exactly what the provider boundary receives."""

    def __init__(self, delegate: GeminiMarketOptionExplanationTextProvider) -> None:
        self._delegate = delegate
        self.payloads: list[MarketOptionExplanationProviderPayload] = []

    def generate_text(
        self,
        *,
        prompt_payload: MarketOptionExplanationProviderPayload,
        run_context: MarketOptionExplanationRunContext,
    ) -> str:
        self.payloads.append(prompt_payload)
        return self._delegate.generate_text(
            prompt_payload=prompt_payload,
            run_context=run_context,
        )


def test_ai_explanation_pipeline_persists_audit_before_release_and_is_owner_scoped() -> None:
    transport = StubGeminiTransport(calls=[])
    provider = RecordingTextProvider(_gemini_adapter(transport))

    with _synthetic_session() as session:
        assessment = _assessment(
            organization_id=session.owner_organization_id,
            policy_id=session.policy_id,
        )
        repository = TransactionalAIExplanationAuditRepository(session.connection)
        audit_context = _audit_record_context()

        result = MarketOptionExplanationPipelineService(
            text_provider=provider,
            audit_repository=repository,
        ).explain(
            assessment=assessment,
            run_context=_run_context(session.owner_organization_id),
            audit_record_context=audit_context,
        )

        assert result.released_text == RELEASABLE_TEXT
        assert result.audit_record is not None
        assert (
            result.audit_record.release_disposition
            is MarketOptionExplanationReleaseDisposition.RELEASE_APPROVED
        )

        persisted = repository.get(audit_context.audit_id)
        assert persisted == result.audit_record
        assert persisted is not None
        assert persisted.record_owner_organization_id == session.owner_organization_id
        assert persisted.reference_time == assessment.context.reference_time
        assert persisted.knowledge_cutoff == assessment.context.knowledge_cutoff
        assert persisted.requested_at == audit_context.requested_at
        assert persisted.evaluated_at == audit_context.evaluated_at
        assert persisted.released_output_digest == result.audit_envelope.released_output_digest

        # Record ownership is derived from the canonical assessment; the caller-provided
        # audit context carries no Organization field to override it with.
        assert {field.name for field in fields(MarketOptionExplanationAuditRecordContext)} == {
            "audit_id",
            "requested_at",
            "evaluated_at",
            "correlation_id",
        }

        stored_row = _stored_row_as_text(session.connection, audit_context.audit_id)
        assert RELEASABLE_TEXT not in stored_row
        assert MARKET_OPTIONALITY_AI_EXPLANATION_PROMPT_TEMPLATE_TEXT not in stored_row
        assert str(assessment.context.subject_id) not in stored_row
        assert str(assessment.decision_id) not in stored_row
        assert str(assessment.evaluation_id) not in stored_row

        assert len(provider.payloads) == 1
        provider_payload = provider.payloads[0]
        assert isinstance(provider_payload, MarketOptionExplanationProviderPayload)
        assert not hasattr(provider_payload, "source_reference_aliases")
        request_body = json.dumps(transport.calls[0]["body"], ensure_ascii=False, default=str)
        assert "source_reference_aliases" not in request_body
        assert str(session.owner_organization_id) not in request_body

        assert repository.find_by_correlation_id(
            record_owner_organization_id=session.owner_organization_id,
            correlation_id=audit_context.correlation_id,
        ) == (persisted,)

        set_local_organization_context(session.connection, session.other_organization_id)
        assert repository.get(audit_context.audit_id) is None
        assert repository.list_for_owner(session.owner_organization_id) == ()
        assert (
            repository.find_by_correlation_id(
                record_owner_organization_id=session.owner_organization_id,
                correlation_id=audit_context.correlation_id,
            )
            == ()
        )


def test_ai_explanation_pipeline_falls_back_and_audits_when_provider_fails() -> None:
    transport = StubGeminiTransport(calls=[], status=503)
    provider = _gemini_adapter(transport)

    with _synthetic_session() as session:
        assessment = _assessment(
            organization_id=session.owner_organization_id,
            policy_id=session.policy_id,
        )
        repository = TransactionalAIExplanationAuditRepository(session.connection)
        audit_context = _audit_record_context()

        result = MarketOptionExplanationPipelineService(
            text_provider=provider,
            audit_repository=repository,
        ).explain(
            assessment=assessment,
            run_context=_run_context(session.owner_organization_id),
            audit_record_context=audit_context,
        )

        assert result.released_text is None
        assert MarketOptionExplanationViolation.PROVIDER_UNAVAILABLE in result.validation.violations
        assert PROVIDER_ERROR_TEXT not in repr(result)
        assert result.canonical_fallback.state is assessment.state
        assert result.canonical_fallback.reference_time == assessment.context.reference_time
        assert result.canonical_fallback.knowledge_cutoff == assessment.context.knowledge_cutoff

        persisted = repository.get(audit_context.audit_id)
        assert persisted is not None
        assert persisted.release_disposition is (
            MarketOptionExplanationReleaseDisposition.NOT_RELEASED
        )
        assert persisted.accepted is False
        assert persisted.released_output_digest is None
        assert persisted.violation_codes == (
            MarketOptionExplanationViolation.PROVIDER_UNAVAILABLE.value,
        )
        assert PROVIDER_ERROR_TEXT not in _stored_row_as_text(
            session.connection,
            audit_context.audit_id,
        )


def test_ai_explanation_pipeline_does_not_release_when_durable_audit_fails() -> None:
    transport = StubGeminiTransport(calls=[])
    provider = _gemini_adapter(transport)

    with _synthetic_session() as session:
        # A Policy that was never persisted makes the audit INSERT fail on its
        # foreign key, exercising a real durable-storage failure.
        assessment = _assessment(
            organization_id=session.owner_organization_id,
            policy_id=TypedId.new("policy"),
        )
        repository = TransactionalAIExplanationAuditRepository(session.connection)
        audit_context = _audit_record_context()

        savepoint = session.connection.begin_nested()
        result = MarketOptionExplanationPipelineService(
            text_provider=provider,
            audit_repository=repository,
        ).explain(
            assessment=assessment,
            run_context=_run_context(session.owner_organization_id),
            audit_record_context=audit_context,
        )
        savepoint.rollback()

        assert result.released_text is None
        assert result.audit_record is None
        assert result.audit_envelope.released_output_digest is None
        assert result.audit_envelope.release_disposition is (
            MarketOptionExplanationReleaseDisposition.NOT_RELEASED
        )
        assert MarketOptionExplanationViolation.AUDIT_PERSISTENCE_FAILED in (
            result.validation.violations
        )
        assert repository.get(audit_context.audit_id) is None
        assert repository.list_for_owner(session.owner_organization_id) == ()


@dataclass(frozen=True, slots=True)
class _SyntheticSession:
    connection: Connection
    owner_organization_id: OrganizationId
    other_organization_id: OrganizationId
    policy_id: TypedId


@contextmanager
def _synthetic_session() -> Iterator[_SyntheticSession]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_ai_explanation_pipeline_{uuid4().hex}"
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

                yield _SyntheticSession(
                    connection=connection,
                    owner_organization_id=owner.organization_id,
                    other_organization_id=other.organization_id,
                    policy_id=policy_id,
                )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _assessment(
    *,
    organization_id: OrganizationId,
    policy_id: TypedId,
) -> MarketOptionAssessment:
    decision, evaluation, policy = _artifacts(
        purpose=PURPOSE,
        organization_id=organization_id,
        policy_id=policy_id,
    )
    return MarketOptionAssessmentService().assess(
        context=_context_from_artifacts(policy, decision),
        decision=decision,
        evaluation=evaluation,
    )


def _run_context(organization_id: OrganizationId) -> MarketOptionExplanationRunContext:
    return MarketOptionExplanationRunContext(
        data_contract_id=MARKET_OPTIONALITY_AI_EXPLANATION_SYNTHETIC_CONTRACT_ID,
        data_contract_version=1,
        processing_activity="SYNTHETIC_AI_EXPLANATION_END_TO_END_VALIDATION",
        processing_authorization_organization_id=organization_id,
        processing_authorization_purpose=PURPOSE,
        provider_profile="GEMINI_SYNTHETIC_VALIDATION_ONLY",
        model_name=MODEL_NAME,
    )


def _audit_record_context() -> MarketOptionExplanationAuditRecordContext:
    return MarketOptionExplanationAuditRecordContext(
        audit_id=TypedId.new("ai_explanation_audit"),
        requested_at=NOW,
        evaluated_at=NOW + timedelta(seconds=1),
        correlation_id=TypedId.new("correlation"),
    )


def _gemini_adapter(
    transport: StubGeminiTransport,
) -> GeminiMarketOptionExplanationTextProvider:
    return GeminiMarketOptionExplanationTextProvider(
        api_key="synthetic-local-key",
        model_name=MODEL_NAME,
        enabled=True,
        transport=transport,
    )


def _stored_row_as_text(connection: Connection, audit_id: TypedId) -> str:
    row = connection.execute(
        text(
            """
            SELECT to_jsonb(record) AS payload
            FROM core_audit.ai_explanation_audit_records AS record
            WHERE audit_id = :audit_id
            """
        ),
        {"audit_id": audit_id.value},
    ).fetchone()
    assert row is not None
    return json.dumps(row.payload, ensure_ascii=False, default=str)


def _insert_policy(connection: Connection, organization_id: OrganizationId) -> TypedId:
    policy_id = TypedId.new("policy")
    connection.execute(
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
                'AI Explanation Pipeline Test Policy',
                'Synthetic policy only for the AI Explanation end-to-end test.',
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
            "code": f"AI_EXPLANATION_PIPELINE_TEST_{uuid4().hex}",
            "valid_from": NOW,
            "created_at": NOW,
            "published_at": NOW,
        },
    )
    return policy_id
