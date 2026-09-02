"""PostgreSQL/RLS tests for Market Supply owner-scoped candidate animal reader."""

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text

from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.authorization_grant import (
    TransactionalAuthorizationGrantRepository,
)
from packages.livestock_application.market_supply_authorization import (
    MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
    MARKET_SUPPLY_AGGREGATE_FIELD_SCOPE,
)
from packages.livestock_application.market_supply_population import (
    AuthorizedCandidatePopulationCompositionService,
    CandidatePopulationCriteria,
    CandidatePopulationResolver,
)
from packages.livestock_infrastructure.persistence.market_supply_population_reader import (
    TransactionalMarketSupplyOwnerScopedSubjectReader,
    TransactionalOwnerScopedCandidateAnimalReader,
)
from packages.shared_kernel import OrganizationId, TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL nao configurada para teste PostgreSQL.",
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)


def test_owner_scoped_candidate_reader_requires_rls_context_and_preserves_temporal_view() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_market_supply_population_{uuid4().hex}"
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

                owner_property = _insert_property(connection, owner.organization_id.value)
                other_property = _insert_property(connection, other.organization_id.value)
                included_animal = _insert_animal(
                    connection,
                    owner.organization_id.value,
                    owner_property,
                    created_at=NOW - timedelta(days=2),
                )
                later_known_animal = _insert_animal(
                    connection,
                    owner.organization_id.value,
                    owner_property,
                    created_at=NOW + timedelta(seconds=1),
                )
                exited_after_reference = _insert_animal(
                    connection,
                    owner.organization_id.value,
                    owner_property,
                    created_at=NOW - timedelta(days=2),
                )
                exited_before_reference = _insert_animal(
                    connection,
                    owner.organization_id.value,
                    owner_property,
                    created_at=NOW - timedelta(days=2),
                )
                other_animal = _insert_animal(
                    connection,
                    other.organization_id.value,
                    other_property,
                    created_at=NOW - timedelta(days=2),
                )
                _insert_exit(
                    connection,
                    owner.organization_id.value,
                    exited_after_reference,
                    occurred_at=NOW + timedelta(days=1),
                )
                _insert_exit(
                    connection,
                    owner.organization_id.value,
                    exited_before_reference,
                    occurred_at=NOW - timedelta(seconds=1),
                )

                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(text(f"GRANT SELECT ON core_audit.animals TO {quoted_role}"))
                connection.execute(
                    text(f"GRANT SELECT ON core_audit.animal_exits TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                criteria = CandidatePopulationCriteria(
                    organization_id=owner.organization_id,
                    purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                    policy_id=TypedId.new("policy"),
                    policy_version=1,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                )

                with pytest.raises(RuntimeError, match="contexto RLS do owner"):
                    TransactionalOwnerScopedCandidateAnimalReader(connection).list_subjects(
                        criteria=criteria,
                    )

                set_local_organization_context(connection, other.organization_id)
                with pytest.raises(RuntimeError, match="contexto RLS do owner"):
                    TransactionalOwnerScopedCandidateAnimalReader(connection).list_subjects(
                        criteria=criteria,
                    )

                set_local_organization_context(connection, owner.organization_id)
                subjects = TransactionalOwnerScopedCandidateAnimalReader(connection).list_subjects(
                    criteria=criteria
                )

                subject_ids = {subject.subject_id.value for subject in subjects}
                assert included_animal in subject_ids
                assert later_known_animal in subject_ids
                assert exited_after_reference in subject_ids
                assert exited_before_reference not in subject_ids
                assert other_animal not in subject_ids
                assert {subject.organization_id for subject in subjects} == {owner.organization_id}

                snapshot = CandidatePopulationResolver().resolve(
                    criteria=criteria,
                    subjects=subjects,
                    resolved_at=NOW,
                )

                assert snapshot.included_count == 2
                assert snapshot.internal_universe_summary().property_count == 1
                assert snapshot.excluded_summary[0].reason == "NOT_KNOWN_AT_CUTOFF"
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_market_supply_composition_reads_authorized_owner_subjects_and_restores_buyer_context() -> (
    None
):
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_market_supply_composition_{uuid4().hex}"
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
                _insert_grant(
                    connection,
                    owner_organization_id=owner.organization_id,
                    beneficiary_organization_id=buyer.organization_id,
                    policy_id=policy_id,
                    policy_version_id=policy_version_id,
                )
                property_id = _insert_property(connection, owner.organization_id.value)
                included_animal = _insert_animal(
                    connection,
                    owner.organization_id.value,
                    property_id,
                    created_at=NOW - timedelta(days=2),
                )

                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOCREATEDB "
                        "NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(text(f"GRANT SELECT ON core_audit.animals TO {quoted_role}"))
                connection.execute(
                    text(f"GRANT SELECT ON core_audit.animal_exits TO {quoted_role}")
                )
                connection.execute(
                    text(f"GRANT SELECT ON core_audit.authorization_grants TO {quoted_role}")
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))

                set_local_organization_context(connection, buyer.organization_id)
                base_criteria = CandidatePopulationCriteria(
                    organization_id=buyer.organization_id,
                    purpose=MARKET_SUPPLY_AGGREGATE_ASSESSMENT,
                    policy_id=policy_id,
                    policy_version=1,
                    reference_time=NOW,
                    knowledge_cutoff=NOW,
                )

                composition = AuthorizedCandidatePopulationCompositionService(
                    grant_reader=TransactionalAuthorizationGrantRepository(connection),
                    subject_reader=TransactionalMarketSupplyOwnerScopedSubjectReader(connection),
                ).compose(
                    buyer_organization_id=buyer.organization_id,
                    base_criteria=base_criteria,
                    requested_at=NOW,
                )

                assert composition.grants_considered == 1
                assert len(composition.result.snapshots) == 1
                snapshot = composition.result.snapshots[0]
                assert snapshot.criteria.organization_id == owner.organization_id
                assert snapshot.included_subject_ids == (TypedId("animal", included_animal),)
                assert _current_organization_id(connection) == buyer.organization_id
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def _insert_property(connection: object, organization_id: UUID) -> UUID:
    property_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.rural_properties (
                property_id, record_owner_organization_id, code, name,
                municipality, state_code, created_at
            ) VALUES (
                :property_id, :organization_id, :code,
                'Market Supply Candidate Property', 'Campo Grande', 'MS', :created_at
            )
            """
        ),
        {
            "property_id": property_id,
            "organization_id": organization_id,
            "code": f"MS-CAND-{uuid4().hex}",
            "created_at": NOW - timedelta(days=10),
        },
    )
    return property_id


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
                'Market Supply Population Test Policy',
                'Synthetic policy only for Market Supply population test.',
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
            "code": f"MARKET_SUPPLY_POPULATION_TEST_{uuid4().hex}",
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
) -> None:
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
                'market-supply-population-test',
                :owner_organization_id
            )
            """
        ),
        {
            "grant_id": uuid4(),
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


def _current_organization_id(connection: object) -> OrganizationId:
    raw = connection.execute(  # type: ignore[attr-defined]
        text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
    ).scalar_one()
    return OrganizationId(raw)


def _insert_animal(
    connection: object,
    organization_id: UUID,
    property_id: UUID,
    *,
    created_at: datetime,
) -> UUID:
    animal_id = uuid4()
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.animals (
                animal_id,
                record_owner_organization_id,
                birth_property_id,
                sex,
                breed,
                birth_date,
                birth_outcome,
                birth_property_source,
                version,
                created_at
            ) VALUES (
                :animal_id,
                :organization_id,
                :property_id,
                'MALE',
                'Nelore',
                NULL,
                'NASCIDO_VIVO',
                'DECLARED',
                1,
                :created_at
            )
            """
        ),
        {
            "animal_id": animal_id,
            "organization_id": organization_id,
            "property_id": property_id,
            "created_at": created_at,
        },
    )
    return animal_id


def _insert_exit(
    connection: object,
    organization_id: UUID,
    animal_id: UUID,
    *,
    occurred_at: datetime,
) -> None:
    connection.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO core_audit.animal_exits (
                exit_id,
                record_owner_organization_id,
                animal_id,
                exit_type,
                occurred_at,
                reason,
                destination,
                evidence_references,
                created_at
            ) VALUES (
                :exit_id,
                :organization_id,
                :animal_id,
                'TRANSFERENCIA',
                :occurred_at,
                NULL,
                NULL,
                '[]',
                :created_at
            )
            """
        ),
        {
            "exit_id": uuid4(),
            "organization_id": organization_id,
            "animal_id": animal_id,
            "occurred_at": occurred_at,
            "created_at": occurred_at,
        },
    )
