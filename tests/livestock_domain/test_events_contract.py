"""Contrato dos eventos da vertical Livestock (Passo 10.1a).

O `event_type` e o nome do schema do payload são contrato público: uma vez
gravados no log append-only do Core, mudá-los quebra a leitura do que já existe.
Estes testes congelam essa superfície.
"""

import re
from datetime import UTC, datetime

import pytest

from packages.core_domain.events import CanonicalPayload
from packages.livestock_domain import events
from packages.shared_kernel import TypedId

EXPECTED_EVENT_TYPES = frozenset(
    {
        "livestock.animal_added_to_lot",
        "livestock.animal_exited",
        "livestock.animal_moved",
        "livestock.animal_registered",
        "livestock.animal_removed_from_lot",
        "livestock.identifier_attached",
        "livestock.identifier_deactivated",
        "livestock.lot_created",
        "livestock.medication_batch_registered",
        "livestock.medication_registered",
        "livestock.prescription_issued",
        "livestock.property_registered",
        "livestock.treatment_applied",
        "livestock.veterinarian_registered",
        "livestock.veterinarian_status_updated",
    }
)


def test_declared_event_types_are_frozen() -> None:
    assert events.LIVESTOCK_EVENT_TYPES == EXPECTED_EVENT_TYPES


def test_every_event_type_is_namespaced_and_canonical() -> None:
    """O prefixo diz de quem é o fato sem precisar abrir o payload.

    O padrão é o mesmo que o `DomainEvent` do Core exige; repeti-lo aqui faz o
    nome fora do padrão falhar no teste do contrato, e não só na gravação.
    """
    canonical = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")

    for event_type in events.LIVESTOCK_EVENT_TYPES:
        assert event_type.startswith("livestock.")
        assert canonical.fullmatch(event_type), event_type


@pytest.mark.parametrize(
    ("builder", "kwargs", "event_type"),
    [
        (
            events.property_registered_payload,
            {
                "property_id": TypedId.new("rural_property"),
                "code": "P-1",
                "name": "Fazenda",
                "municipality": "Uberaba",
                "state_code": "MG",
                "registration_number": None,
                "total_area_hectares": None,
            },
            events.PROPERTY_REGISTERED,
        ),
        (
            events.animal_registered_payload,
            {
                "animal_id": TypedId.new("animal"),
                "birth_property_id": TypedId.new("rural_property"),
                "sex": "MACHO",
                "breed": None,
                "birth_date": None,
            },
            events.ANIMAL_REGISTERED,
        ),
        (
            events.medication_batch_registered_payload,
            {
                "batch_id": TypedId.new("medication_batch"),
                "medication_id": TypedId.new("medication"),
                "batch_number": "L-1",
                "expiry_date": datetime(2027, 1, 1, tzinfo=UTC),
                "manufacturing_date": None,
            },
            events.MEDICATION_BATCH_REGISTERED,
        ),
        (
            events.treatment_applied_payload,
            {
                "application_id": TypedId.new("treatment_application"),
                "animal_id": TypedId.new("animal"),
                "medication_batch_id": TypedId.new("medication_batch"),
                "applied_at": datetime(2026, 7, 1, tzinfo=UTC),
                "dose": None,
                "prescription_id": None,
                "evidence_references": (),
                "evidence_notes": (),
                "corrects_application_id": None,
            },
            events.TREATMENT_APPLIED,
        ),
    ],
)
def test_payload_schema_derives_from_the_event_type(
    builder: object, kwargs: dict[str, object], event_type: str
) -> None:
    """Schema e event_type saem da mesma fonte, então não podem divergir."""
    payload = builder(**kwargs)  # type: ignore[operator]

    assert isinstance(payload, CanonicalPayload)
    assert payload.schema == f"{event_type.replace('.', '_')}_payload"
    assert payload.version == events.PAYLOAD_VERSION


def test_payload_is_deterministic_for_the_same_content() -> None:
    """Mesmo conteúdo, mesmos bytes: é o que permite comparar e reproduzir."""
    animal_id = TypedId.new("animal")
    property_id = TypedId.new("rural_property")
    arguments = {
        "animal_id": animal_id,
        "birth_property_id": property_id,
        "sex": "FEMEA",
        "breed": "Nelore",
        "birth_date": "2024-03-01",
    }

    first = events.animal_registered_payload(**arguments)  # type: ignore[arg-type]
    second = events.animal_registered_payload(**arguments)  # type: ignore[arg-type]

    assert first.canonical_bytes == second.canonical_bytes


def test_area_is_converted_because_the_serializer_refuses_float() -> None:
    payload = events.property_registered_payload(
        property_id=TypedId.new("rural_property"),
        code="P-1",
        name="Fazenda",
        municipality="Uberaba",
        state_code="MG",
        registration_number=None,
        total_area_hectares=250.5,
    )

    assert b"250.5" in payload.canonical_bytes
