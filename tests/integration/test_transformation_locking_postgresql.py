"""Bloqueio transacional para correção de TransformationEvent (ADR-0047, item 5).

Prova duas coisas que nenhum teste de domínio/aplicação consegue provar sem um
Postgres real: (1) `lock_*` devolve `True`/`False` conforme a linha existe, e
(2) o `SELECT ... FOR UPDATE` realmente serializa duas transações concorrentes
disputando a mesma linha — a garantia central que o protocolo de correção da
ADR-0047 depende.
"""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine

from packages.livestock_domain.animal import AnimalSex
from packages.livestock_domain.transformation import (
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationEvent,
    TransformationParticipant,
)
from packages.livestock_infrastructure.persistence.transformation_locking import (
    TransactionalTransformationLock,
)
from packages.livestock_infrastructure.persistence.transformation_repository import (
    TransactionalTraceableItemRepository,
    TransactionalTransformationEventRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

DATABASE_URL = os.environ.get(
    "TITAN_DATABASE_URL",
    "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL.",
)

MOMENTO = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        yield eng
    finally:
        eng.dispose()


def _reference(organization_id: OrganizationId, entity_type: str) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=organization_id, contract_version=1
    )


def _setup_organization(connection: Connection, organization_id: OrganizationId) -> None:
    connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations
                (organization_id, record_owner_organization_id)
            VALUES (:org, :org)
            """
        ),
        {"org": organization_id.value},
    )
    connection.execute(
        text("SELECT set_config('titan.organization_id', :org, true)"),
        {"org": str(organization_id.value)},
    )


def _insert_animal(
    connection: Connection, organization_id: OrganizationId, animal_id: TypedId
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO core_audit.animals
                (animal_id, record_owner_organization_id, sex, birth_property_source, created_at)
            VALUES (:animal_id, :org, :sex, 'UNKNOWN', :created_at)
            """
        ),
        {
            "animal_id": animal_id.value,
            "org": organization_id.value,
            "sex": AnimalSex.MALE.value,
            "created_at": MOMENTO,
        },
    )


def _create_event(connection: Connection, organization_id: OrganizationId) -> TypedId:
    event = TransformationEvent(
        event_id=TypedId.new("transformation_event"),
        organization_id=organization_id,
        process_type=ProcessType.SLAUGHTER,
        occurred_at=MOMENTO,
        facility_reference=_reference(organization_id, "rural_property"),
        inputs=(
            TransformationParticipant(
                subject_reference=_reference(organization_id, "animal"),
                role=ParticipantRole.INPUT,
            ),
        ),
        outputs=(
            TransformationParticipant(
                subject_reference=_reference(organization_id, "traceable_item"),
                role=ParticipantRole.OUTPUT,
                quantity=Decimal("100"),
                unit="kg",
            ),
            TransformationParticipant(
                subject_reference=_reference(organization_id, "traceable_item"),
                role=ParticipantRole.OUTPUT,
                quantity=Decimal("50"),
                unit="kg",
            ),
        ),
        created_at=MOMENTO,
    )
    TransactionalTransformationEventRepository(connection).save(event)
    return event.event_id


def _create_item(
    connection: Connection, organization_id: OrganizationId, created_by: TypedId
) -> TypedId:
    item = TraceableItem(
        item_id=TypedId.new("traceable_item"),
        organization_id=organization_id,
        item_type=TraceableItemType.HALF_CARCASS,
        created_by_transformation_id=created_by,
        created_at=MOMENTO,
    )
    TransactionalTraceableItemRepository(connection).save(item)
    return item.item_id


def test_lock_transformation_event_existente_e_inexistente(engine: Engine) -> None:
    organization_id = OrganizationId(uuid4())
    with engine.begin() as connection:
        _setup_organization(connection, organization_id)
        event_id = _create_event(connection, organization_id)

        lock = TransactionalTransformationLock(connection)
        assert lock.lock_transformation_event(event_id) is True
        assert lock.lock_transformation_event(TypedId.new("transformation_event")) is False


def test_lock_traceable_item_existente_e_inexistente(engine: Engine) -> None:
    organization_id = OrganizationId(uuid4())
    with engine.begin() as connection:
        _setup_organization(connection, organization_id)
        event_id = _create_event(connection, organization_id)
        item_id = _create_item(connection, organization_id, event_id)

        lock = TransactionalTransformationLock(connection)
        assert lock.lock_traceable_item(item_id) is True
        assert lock.lock_traceable_item(TypedId.new("traceable_item")) is False


def test_lock_animal_existente_e_inexistente(engine: Engine) -> None:
    organization_id = OrganizationId(uuid4())
    with engine.begin() as connection:
        _setup_organization(connection, organization_id)
        animal_id = TypedId.new("animal")
        _insert_animal(connection, organization_id, animal_id)

        lock = TransactionalTransformationLock(connection)
        assert lock.lock_animal(animal_id) is True
        assert lock.lock_animal(TypedId.new("animal")) is False


def test_lock_serializa_transacoes_concorrentes_na_mesma_linha(engine: Engine) -> None:
    organization_id = OrganizationId(uuid4())
    with engine.connect() as setup_connection:
        with setup_connection.begin():
            _setup_organization(setup_connection, organization_id)
            event_id = _create_event(setup_connection, organization_id)

    barrier = Barrier(2)
    ordem: list[str] = []

    def segura_e_libera_depois(rotulo: str, espera_segundos: float) -> None:
        with engine.begin() as connection:
            connection.execute(
                text("SELECT set_config('titan.organization_id', :org, true)"),
                {"org": str(organization_id.value)},
            )
            barrier.wait(timeout=5)
            TransactionalTransformationLock(connection).lock_transformation_event(event_id)
            ordem.append(f"{rotulo}:adquiriu")
            if espera_segundos:
                import time

                time.sleep(espera_segundos)
            ordem.append(f"{rotulo}:liberou")

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(segura_e_libera_depois, "A", 0.5)
        future_b = executor.submit(segura_e_libera_depois, "B", 0.0)
        future_a.result(timeout=10)
        future_b.result(timeout=10)

    # Quem quer que tenha adquirido primeiro precisa ter liberado (commit) antes
    # que o outro consiga adquirir — nunca as duas aquisições intercaladas.
    primeira_aquisicao = ordem[0]
    rotulo_primeiro = primeira_aquisicao.split(":")[0]
    indice_liberacao_primeiro = ordem.index(f"{rotulo_primeiro}:liberou")
    indice_aquisicao_segundo = next(
        indice
        for indice, entrada in enumerate(ordem)
        if entrada.endswith(":adquiriu") and not entrada.startswith(rotulo_primeiro)
    )
    assert indice_liberacao_primeiro < indice_aquisicao_segundo
