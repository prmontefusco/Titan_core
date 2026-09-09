"""PostgreSQL API integration for the Market Supply F3.5 aggregate route."""

import importlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, text

from apps.api.livestock_dependencies import request_connection
from packages.core_domain import AuthenticatedPrincipal, Organization, OrganizationContext
from packages.core_domain.authentication import PrincipalType
from packages.core_domain.decision import (
    Decision,
    DecisionReason,
    DecisionReasonCode,
    DecisionResult,
    compute_decision_hash,
)
from packages.core_domain.decision_authority import DecisionEmissionMethod
from packages.core_domain.decision_governance import DecisionAuthorityProfile
from packages.core_domain.evaluation import Evaluation, EvaluationOutcome, compute_context_hash
from packages.core_domain.facts import FactSnapshot
from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy, PolicyStatus
from packages.core_domain.policy_sharing import AuthorizationGrant
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.decision_governance import (
    TransactionalDecisionAuthorityProfileRepository,
)
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.livestock_application.authorization import MARKET_SUPPLY_AGGREGATE_ASSESS
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    rural_properties_table,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL nao configurada para teste PostgreSQL.",
)

ROUTE = "/v1/livestock/market-supply/aggregate-assessments"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_market_supply_aggregate_route_releases_real_single_owner_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role = os.environ.get("TITAN_RUNTIME_DATABASE_ROLE", "titan_app")
    previous_env = {
        key: os.environ.get(key)
        for key in (
            "TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED",
            "TITAN_MARKET_SUPPLY_AGGREGATE_PIPELINE_ENABLED",
            "TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID",
            "TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES",
            "TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS",
            "TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW",
            "TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS",
        )
    }

    try:
        _enable_market_supply_route(monkeypatch)
        import apps.api.main as main_module
        from apps.api import livestock_market_supply as market_supply_api

        importlib.reload(main_module)
        idempotency_key = f"market-supply-api-test-{uuid4()}"
        with engine.begin() as connection:
            owner = Organization.create()
            buyer = Organization.create()
            for organization in (owner, buyer):
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)

            policy = _save_policy(connection, owner.organization_id)
            property_id = _save_property(connection, owner.organization_id)
            animals = _save_ready_animals(
                connection,
                organization_id=owner.organization_id,
                property_id=property_id,
                policy=policy,
                count=3,
            )
            grant = AuthorizationGrant(
                grant_id=uuid4(),
                owner_organization_id=owner.organization_id,
                beneficiary_organization_id=buyer.organization_id,
                policy_id=policy.policy_id,
                policy_version_id=TypedId.new("policy_version"),
                access_purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                field_scope_profile=MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
                valid_from=NOW - timedelta(days=1),
                valid_until=NOW + timedelta(days=30),
                status="ATIVO",
                created_at=NOW - timedelta(days=1),
                created_by="market-supply-api-test",
                record_owner_organization_id=owner.organization_id,
            )
            set_local_organization_context(connection, owner.organization_id)
            TransactionalAuthorizationGrantRepository(connection).save(grant)

        buyer_context = _buyer_context(buyer.organization_id)
        main_module.app.dependency_overrides[
            market_supply_api.require_market_supply_aggregate_assess
        ] = lambda: buyer_context

        def runtime_connection() -> Iterator[Connection]:
            with engine.connect() as request_connection_handle:
                with request_connection_handle.begin():
                    yield from _runtime_connection(
                        request_connection_handle,
                        role,
                        buyer.organization_id,
                    )

        main_module.app.dependency_overrides[request_connection] = runtime_connection
        client = TestClient(main_module.app, raise_server_exceptions=False)
        response = client.post(
            ROUTE,
            headers={"Idempotency-Key": idempotency_key},
            json=_request_body(policy.policy_id),
        )
        replay = client.post(
            ROUTE,
            headers={"Idempotency-Key": idempotency_key},
            json=_request_body(policy.policy_id),
        )

        assert response.status_code == 200, response.text
        assert replay.status_code == 200, replay.text
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == replay.json()
        assert response.json()["status"] == "RELEASED"
        assert response.json()["aggregate"]["population_count"] == len(animals)
        assert response.json()["aggregate"]["ready_now"] == len(animals)
        assert response.json()["aggregate"]["estimated_shortage_now"] == 2

        with engine.connect() as connection:
            with connection.begin():
                quoted_role = connection.dialect.identifier_preparer.quote(role)
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                set_local_organization_context(connection, owner.organization_id)
                audit_count = connection.execute(
                    text(
                        """
                        SELECT count(*)
                          FROM core_audit.market_supply_query_audit_records
                         WHERE idempotency_reference = :key
                        """
                    ),
                    {"key": idempotency_key},
                ).scalar_one()
                assert audit_count == 1

                set_local_organization_context(connection, buyer.organization_id)
                buyer_visible_audit_count = connection.execute(
                    text(
                        """
                        SELECT count(*)
                          FROM core_audit.market_supply_query_audit_records
                         WHERE idempotency_reference = :key
                        """
                    ),
                    {"key": idempotency_key},
                ).scalar_one()
                assert buyer_visible_audit_count == 0
                connection.execute(text("RESET ROLE"))
        main_module.app.dependency_overrides.clear()
    finally:
        for key, value in previous_env.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        engine.dispose()


def _enable_market_supply_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED", "true")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_AGGREGATE_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_PROFILE_ID", "market-supply-api-test")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_POLICY_VERSION", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_ORGANIZATIONS", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_PROPERTIES", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MINIMUM_SUBJECTS", "1")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_MAX_FILTER_COUNT_WITHOUT_REVIEW", "10")
    monkeypatch.setenv("TITAN_MARKET_SUPPLY_PRIVACY_REPEATED_QUERY_WINDOW_SECONDS", "60")


def _runtime_connection(
    connection: Connection,
    role: str,
    organization_id: OrganizationId,
) -> Iterator[Connection]:
    quoted_role = connection.dialect.identifier_preparer.quote(role)
    connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    set_local_organization_context(connection, organization_id)
    try:
        yield connection
        assert _current_organization_id(connection) == organization_id
    finally:
        connection.execute(text("RESET ROLE"))


def _current_organization_id(connection: Connection) -> OrganizationId | None:
    raw = connection.execute(
        text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
    ).scalar_one_or_none()
    if raw is None:
        return None
    return OrganizationId(raw)


def _buyer_context(organization_id: OrganizationId) -> OrganizationContext:
    principal = AuthenticatedPrincipal(
        issuer="https://issuer.example.test",
        subject="market-supply-api-test-user",
        principal_type=PrincipalType.USER,
        authenticated_at=NOW,
        client_id="market-supply-api-test",
        technical_scopes=frozenset({"openid"}),
    )
    return OrganizationContext(
        organization_id=organization_id,
        authenticated_principal=principal,
        user_id=TypedId.new("user"),
        actor_id=TypedId.new("actor"),
        membership_id=TypedId.new("membership"),
        role_ids=(TypedId.new("role"),),
        permission_codes=frozenset({MARKET_SUPPLY_AGGREGATE_ASSESS}),
        validated_at=NOW,
    )


def _save_policy(connection: Connection, organization_id: OrganizationId) -> Policy:
    policy = Policy(
        policy_id=TypedId.new("policy"),
        organization_id=organization_id,
        code=f"MARKET_SUPPLY_API_TEST_{uuid4().hex}",
        name="Market Supply API Test Policy",
        description="Synthetic policy only for Market Supply API integration test.",
        version=1,
        status=PolicyStatus.PUBLISHED,
        valid_from=NOW,
        published_at=NOW,
    )
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
                :name,
                :description,
                :version,
                :status,
                :valid_from,
                NULL,
                :created_at,
                :published_at
            )
            """
        ),
        {
            "policy_id": policy.policy_id.value,
            "organization_id": organization_id.value,
            "code": policy.code,
            "name": policy.name,
            "description": policy.description,
            "version": policy.version,
            "status": policy.status.value,
            "valid_from": policy.valid_from,
            "created_at": NOW,
            "published_at": policy.published_at,
        },
    )
    return policy


def _save_property(connection: Connection, organization_id: OrganizationId) -> TypedId:
    property_id = TypedId.new("rural_property")
    connection.execute(
        rural_properties_table.insert().values(
            property_id=property_id.value,
            record_owner_organization_id=organization_id.value,
            code=f"MARKET-SUPPLY-{uuid4().hex[:8]}",
            name="Synthetic Market Supply Property",
            municipality="Campo Grande",
            state_code="MS",
            created_at=NOW,
        )
    )
    return property_id


def _save_ready_animals(
    connection: Connection,
    *,
    organization_id: OrganizationId,
    property_id: TypedId,
    policy: Policy,
    count: int,
) -> tuple[TypedId, ...]:
    set_local_organization_context(connection, organization_id)
    authority = DecisionAuthorityProfile(
        authority_id=TypedId.new("authority_profile"),
        organization_id=organization_id,
        principal_reference=UniversalReference(TypedId.new("service_identity"), organization_id, 1),
        role_name="market-supply-api-test",
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        emission_method=DecisionEmissionMethod.AUTOMATED,
        valid_from=NOW - timedelta(days=1),
        valid_to=NOW + timedelta(days=30),
    )
    TransactionalDecisionAuthorityProfileRepository(connection).save(authority)
    animal_ids: list[TypedId] = []
    for _ in range(count):
        animal = Animal(
            animal_id=TypedId.new("animal"),
            organization_id=organization_id,
            birth_property_id=property_id,
            sex=AnimalSex.FEMALE,
            breed="Nelore",
            created_at=NOW - timedelta(days=1),
        )
        TransactionalAnimalRepository(connection).save(animal)
        decision, evaluation = _ready_artifacts(
            organization_id=organization_id,
            subject_id=animal.animal_id,
            policy=policy,
            authority_id=authority.authority_id,
        )
        TransactionalEvaluationRepository(connection).save(evaluation)
        TransactionalDecisionRepository(connection).save(decision)
        animal_ids.append(animal.animal_id)
    return tuple(animal_ids)


def _ready_artifacts(
    *,
    organization_id: OrganizationId,
    subject_id: TypedId,
    policy: Policy,
    authority_id: TypedId,
) -> tuple[Decision, Evaluation]:
    snapshot = FactSnapshot.create(
        organization_id=organization_id,
        target_id=subject_id,
        as_of=NOW,
        facts=(),
        reference_time=NOW,
        knowledge_cutoff=NOW,
    )
    rule_versions = (("market-supply-api-test-rule", 1),)
    normative_snapshot = NormativeBasisSnapshot(
        schema_version=1,
        normative_basis_id=TypedId.new("normative_basis"),
        normative_basis_code="MARKET_SUPPLY_API_TEST_BASIS",
        normative_basis_version=1,
        policy_id=policy.policy_id,
        policy_code=policy.code,
        policy_version=policy.version,
        rule_versions=rule_versions,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        jurisdiction="TEST",
        intended_use="MARKET_SUPPLY_API_INTEGRATION_TEST_ONLY",
        reference_time=NOW,
        knowledge_cutoff=NOW,
        approved_by="market-supply-api-test",
        approval_authority="internal-test",
        approved_at=NOW,
        references=(
            NormativeReferenceSnapshot(
                instrument_code="MARKET_SUPPLY_API_TEST",
                instrument_version="1",
                provision="1",
                content_digest="a" * 64,
                digest_algorithm="sha256",
                source_classification=NormativeSourceClassification.INTERNAL_TEST,
            ),
        ),
        limitations=("RECOGNITION_BOUNDARY:INTERNAL_ONLY",),
    )
    context_hash = compute_context_hash(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        engine_version=1,
        rule_versions=rule_versions,
        normative_basis_snapshot_digest=normative_snapshot.snapshot_digest,
    )
    evaluation = Evaluation(
        evaluation_id=TypedId.new("evaluation"),
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        fact_snapshot=snapshot,
        rule_results=(),
        outcome=EvaluationOutcome.CONDICOES_SATISFEITAS,
        evaluated_at=NOW,
        engine_version=1,
        evaluation_hash="b" * 64,
        context_hash=context_hash,
        normative_basis_snapshot=normative_snapshot,
        rule_versions=rule_versions,
    )
    reason = DecisionReason(
        code=DecisionReasonCode.REGRA_ATENDIDA,
        message="Synthetic rule satisfied for Market Supply API integration test.",
        rule_code="market-supply-api-test-rule",
    )
    decision = Decision(
        decision_id=TypedId.new("decision"),
        organization_id=organization_id,
        subject_id=subject_id,
        purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        evaluation_id=evaluation.evaluation_id,
        evaluation_hash=evaluation.evaluation_hash,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        result=DecisionResult.APROVADA,
        reasons=(reason,),
        snapshot_hash=snapshot.snapshot_hash,
        issued_at=NOW,
        engine_version=1,
        decision_hash=compute_decision_hash(
            evaluation_hash=evaluation.evaluation_hash,
            subject_id=subject_id,
            purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
            result=DecisionResult.APROVADA,
            reasons=(reason,),
            authority_profile_id=authority_id,
            emission_method=DecisionEmissionMethod.AUTOMATED,
        ),
        authority_profile_id=authority_id,
        authority_reference=UniversalReference(TypedId.new("service_identity"), organization_id, 1),
        emission_method=DecisionEmissionMethod.AUTOMATED,
    )
    return decision, evaluation


def _request_body(policy_id: TypedId) -> dict[str, object]:
    return {
        "policy_id": str(policy_id.value),
        "policy_version": 1,
        "purpose": MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
        "quantity": 5,
        "commercial_window": {
            "from": "2026-09-01T00:00:00Z",
            "until": "2026-10-15T00:00:00Z",
        },
        "reference_time": "2026-08-31T12:00:00Z",
        "knowledge_cutoff": "2026-08-31T12:00:00Z",
        "candidate_criteria": {
            "subject_type": "animal",
            "required_tags": [],
        },
    }
