import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from packages.core_domain import CanonicalPayload, DomainEvent, Organization
from packages.core_infrastructure.persistence import (
    DomainEventRepository,
    EventAppendConflict,
    EventIntegrityEd25519Signer,
    OrganizationRepository,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId, RecordTimestamps, TypedId, UniversalReference

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)


def _reference(
    entity_type: str, organization_id: OrganizationId, *, identifier: TypedId | None = None
) -> UniversalReference:
    return UniversalReference(
        target_id=identifier or TypedId.new(entity_type),
        organization_id=organization_id,
        contract_version=1,
    )


def _event(
    *, organization_id: OrganizationId, aggregate: UniversalReference, version: int
) -> DomainEvent:
    return DomainEvent(
        event_id=TypedId.new("domain_event"),
        organization_id=organization_id,
        aggregate_reference=aggregate,
        aggregate_version=version,
        event_type="registro_criado",
        event_version=1,
        timestamps=RecordTimestamps(
            occurred_at=datetime(2026, 7, 21, 12, version, tzinfo=UTC),
            recorded_at=datetime(2026, 7, 21, 13, version, tzinfo=UTC),
        ),
        actor_reference=_reference("actor", organization_id),
        source_reference=_reference("source", organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=CanonicalPayload.from_mapping(
            schema="registro_criado_payload",
            version=1,
            value={"versao": version},
        ),
    )


def test_event_store_orders_versions_rejects_gaps_and_isolates_organizations() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    first_organization = Organization.create()
    second_organization = Organization.create()
    aggregate_id = TypedId.new("registro")
    first_aggregate = _reference(
        "registro", first_organization.organization_id, identifier=aggregate_id
    )
    second_aggregate = _reference(
        "registro", second_organization.organization_id, identifier=aggregate_id
    )
    role_name = f"titan_event_isolation_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} "
                        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(
                    text(f"GRANT USAGE ON SCHEMA core_identity, core_audit TO {quoted_role}")
                )
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT ON core_identity.organizations, "
                        f"core_audit.domain_events, core_audit.domain_event_integrity "
                        f"TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                organizations = OrganizationRepository(connection)
                set_local_organization_context(connection, first_organization.organization_id)
                organizations.add(first_organization)
                events = DomainEventRepository(connection)
                events.append(
                    _event(
                        organization_id=first_organization.organization_id,
                        aggregate=first_aggregate,
                        version=1,
                    )
                )
                events.append(
                    _event(
                        organization_id=first_organization.organization_id,
                        aggregate=first_aggregate,
                        version=2,
                    )
                )
                with pytest.raises(EventAppendConflict, match="VERSAO_DE_AGREGADO_CONFLITANTE"):
                    events.append(
                        _event(
                            organization_id=first_organization.organization_id,
                            aggregate=first_aggregate,
                            version=4,
                        )
                    )
                assert [
                    item.aggregate_version for item in events.list_for_aggregate(first_aggregate)
                ] == [1, 2]
                stored_chain = events.list_for_aggregate(first_aggregate)
                assert stored_chain[0].previous_hash is None
                assert stored_chain[0].current_hash == stored_chain[1].previous_hash
                assert stored_chain[1].current_hash is not None
                assert stored_chain[0].signature_algorithm == "ED25519"
                assert stored_chain[0].signature_profile == "titan-event-integrity-signature"
                assert stored_chain[0].signature_key_id is not None
                assert stored_chain[0].signature_public_key is not None
                assert len(stored_chain[0].signature_public_key) == 32
                assert stored_chain[0].signature_bytes is not None
                assert len(stored_chain[0].signature_bytes) == 64
                assert stored_chain[0].signature_signed_at is not None
                canonical = events.list_canonical_for_aggregate(first_aggregate)
                assert [item.aggregate_version for item in canonical] == [1, 2]
                assert (
                    canonical[0].payload_canonical_bytes
                    == events.list_for_aggregate(first_aggregate)[0].payload_canonical_bytes
                )
                assert (
                    canonical[0].payload_digest
                    == hashlib.sha256(canonical[0].payload_canonical_bytes).hexdigest()
                )
                assert canonical[0].integrity_hash == canonical[0].current_hash
                assert not hasattr(canonical[0], "known_at")

                set_local_organization_context(connection, second_organization.organization_id)
                organizations.add(second_organization)
                assert events.list_for_aggregate(first_aggregate) == ()
                assert events.list_canonical_for_aggregate(first_aggregate) == ()
                events.append(
                    _event(
                        organization_id=second_organization.organization_id,
                        aggregate=second_aggregate,
                        version=1,
                    )
                )
                assert [
                    item.aggregate_version for item in events.list_for_aggregate(second_aggregate)
                ] == [1]
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_runtime_role_cannot_update_delete_or_truncate_events() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    role_name = f"titan_event_runtime_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role_name)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)
                connection.execute(
                    text(
                        f"CREATE ROLE {quoted_role} "
                        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                )
                connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
                connection.execute(
                    text(
                        f"GRANT SELECT, INSERT ON core_audit.domain_events, "
                        f"core_audit.domain_event_integrity TO {quoted_role}"
                    )
                )
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
                DomainEventRepository(connection).append(
                    _event(
                        organization_id=organization.organization_id,
                        aggregate=aggregate,
                        version=1,
                    )
                )
                for statement in (
                    "UPDATE core_audit.domain_events SET event_version = 2",
                    "DELETE FROM core_audit.domain_events",
                    "TRUNCATE core_audit.domain_events",
                    "UPDATE core_audit.domain_event_integrity SET hash_profile_version = 2",
                    "UPDATE core_audit.domain_event_integrity SET signature_key_id = 'tampered'",
                    "DELETE FROM core_audit.domain_event_integrity",
                    "TRUNCATE core_audit.domain_event_integrity",
                ):
                    savepoint = connection.begin_nested()
                    with pytest.raises(ProgrammingError):
                        connection.execute(text(statement))
                    savepoint.rollback()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


def test_event_integrity_uses_configured_ed25519_key_for_new_links() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro", organization.organization_id)
    signer = EventIntegrityEd25519Signer.from_environment()

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                set_local_organization_context(connection, organization.organization_id)
                OrganizationRepository(connection).add(organization)
                DomainEventRepository(connection, signer=signer).append(
                    _event(
                        organization_id=organization.organization_id,
                        aggregate=aggregate,
                        version=1,
                    )
                )

                stored = DomainEventRepository(connection).list_for_aggregate(aggregate)

                assert len(stored) == 1
                assert stored[0].signature_algorithm == "ED25519"
                assert stored[0].signature_profile == "titan-event-integrity-signature"
                assert stored[0].signature_key_id == signer.key_id
                assert stored[0].signature_public_key is not None
                assert stored[0].signature_bytes is not None
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


# --- concorrência da cadeia de integridade (decisão F de DECISIONS_REQUIRED_PHASE0.md) ---
#
# `DomainEventRepository.append` serializa via `pg_advisory_xact_lock` numa chave
# `f"{organization_id}:{aggregate_type}:{aggregate_id}"` (events.py). Isso prova
# que a cadeia de integridade é uma garantia **por agregado**, não uma cadeia
# global por Organization: duas verticais no mesmo tenant, escrevendo em tipos de
# agregado diferentes (ex.: `WorkOrder` de Asset e `Animal` de Livestock), nunca
# disputam o mesmo advisory lock e nunca esperam uma pela outra. Os dois testes
# abaixo usam conexões e transações reais e independentes por thread — a mesma
# técnica de `tests/integration/test_transformation_locking_postgresql.py` — porque
# nenhum teste de domínio/aplicação prova serialização real do PostgreSQL.


def test_concurrent_appends_to_the_same_aggregate_serialize_via_advisory_lock() -> None:
    """Duas escritas concorrentes no MESMO agregado nunca corrompem a cadeia.

    Prova a metade "positiva" da decisão F: dentro de um agregado (uma vertical,
    uma instância), a serialização continua garantida sob concorrência real —
    exatamente um `append` de `aggregate_version=1` vence; o outro recebe
    `EventAppendConflict` porque, ao adquirir o lock após o primeiro liberar
    (commit), a versão corrente já não é `None`.
    """
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate = _reference("registro_concorrente", organization.organization_id)

    with engine.connect() as setup_connection:
        with setup_connection.begin():
            set_local_organization_context(setup_connection, organization.organization_id)
            OrganizationRepository(setup_connection).add(organization)

    barrier = Barrier(2)
    resultados: dict[str, bool] = {}

    def tenta_anexar_versao_um(rotulo: str, espera_apos_segundos: float) -> None:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            barrier.wait(timeout=5)
            try:
                DomainEventRepository(connection).append(
                    _event(
                        organization_id=organization.organization_id,
                        aggregate=aggregate,
                        version=1,
                    )
                )
                resultados[rotulo] = True
            except EventAppendConflict:
                resultados[rotulo] = False
            if espera_apos_segundos:
                time.sleep(espera_apos_segundos)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futuro_a = executor.submit(tenta_anexar_versao_um, "A", 0.4)
            futuro_b = executor.submit(tenta_anexar_versao_um, "B", 0.0)
            futuro_a.result(timeout=10)
            futuro_b.result(timeout=10)

        # Exatamente um dos dois conseguiu inserir a versão 1 — o lock impede que
        # ambos vejam "agregado vazio" e tentem a mesma versão ao mesmo tempo.
        assert sorted(resultados.values()) == [False, True]

        with engine.connect() as verify_connection:
            with verify_connection.begin():
                set_local_organization_context(verify_connection, organization.organization_id)
                stored = DomainEventRepository(verify_connection).list_for_aggregate(aggregate)
        assert [item.aggregate_version for item in stored] == [1]
    finally:
        engine.dispose()


def test_concurrent_appends_to_different_aggregates_do_not_serialize() -> None:
    """Duas escritas concorrentes em agregados DIFERENTES não esperam uma pela outra.

    Esta é a prova central da decisão F. A thread A segura sua transação aberta
    por 0.4s depois do `append` (simula uma escrita "lenta" de uma vertical). Se a
    cadeia de integridade fosse uma trava única por Organization (a preocupação
    original de H1), a thread B — outro tipo de agregado, mesma Organization —
    teria que esperar A liberar. Com o lock por `(organization, aggregate_type,
    aggregate_id)`, B termina e comita antes de A, porque as chaves de advisory
    lock são diferentes.
    """
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    organization = Organization.create()
    aggregate_vertical_a = _reference("work_order", organization.organization_id)
    aggregate_vertical_b = _reference("animal", organization.organization_id)

    with engine.connect() as setup_connection:
        with setup_connection.begin():
            set_local_organization_context(setup_connection, organization.organization_id)
            OrganizationRepository(setup_connection).add(organization)

    barrier = Barrier(2)
    ordem: list[str] = []

    def anexa_e_registra(
        rotulo: str, aggregate: UniversalReference, espera_apos_segundos: float
    ) -> None:
        with engine.begin() as connection:
            set_local_organization_context(connection, organization.organization_id)
            barrier.wait(timeout=5)
            DomainEventRepository(connection).append(
                _event(
                    organization_id=organization.organization_id,
                    aggregate=aggregate,
                    version=1,
                )
            )
            if espera_apos_segundos:
                time.sleep(espera_apos_segundos)
        ordem.append(f"{rotulo}:commit")

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            # A ("work_order", uma vertical) fica ocupada por 0.4s após o append,
            # ainda dentro da transação — só libera o advisory lock no commit.
            futuro_a = executor.submit(anexa_e_registra, "A", aggregate_vertical_a, 0.4)
            futuro_b = executor.submit(anexa_e_registra, "B", aggregate_vertical_b, 0.0)
            futuro_a.result(timeout=10)
            futuro_b.result(timeout=10)

        assert ordem.index("B:commit") < ordem.index("A:commit"), (
            "B (agregado diferente) esperou A liberar — a cadeia de integridade "
            "está serializando entre agregados/verticais diferentes; isso "
            "contradiz a decisão F e precisa de investigação em events.py."
        )

        with engine.connect() as verify_connection:
            with verify_connection.begin():
                set_local_organization_context(verify_connection, organization.organization_id)
                events = DomainEventRepository(verify_connection)
                chain_a = events.list_for_aggregate(aggregate_vertical_a)
                chain_b = events.list_for_aggregate(aggregate_vertical_b)
        assert [item.aggregate_version for item in chain_a] == [1]
        assert [item.aggregate_version for item in chain_b] == [1]
        assert chain_a[0].previous_hash is None
        assert chain_b[0].previous_hash is None
    finally:
        engine.dispose()
