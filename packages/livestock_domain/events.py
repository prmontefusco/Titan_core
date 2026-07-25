"""Contrato de eventos de domínio da vertical Titan Livestock (Passo 10.1a).

Um evento da vertical é um `DomainEvent` do Core — não uma subclasse dele. O
repositório do Core grava `event_type` e os bytes canônicos do payload
(`core_infrastructure/persistence/events.py`); campos declarados numa subclasse
não têm coluna e não sobreviveriam à gravação. As antigas subclasses deste
módulo nunca puderam ser usadas por isso, e foram substituídas pelo par
`event_type` + construtor de payload, que é o padrão que o próprio Core segue em
`core_domain/corrections.py`.

O `event_type` é namespaced em `livestock.` para que o log do Core continue
dizendo de quem é cada fato sem inspecionar payload.

**Agregado de cada evento:** é a entidade criada ou alterada pela operação. Uma
movimentação pertence ao `animal_movement`, não a cada animal citado; a inclusão
em lote pertence ao `livestock_lot`. Quem monta a linha do tempo de um animal
reúne os fluxos das entidades relacionadas — o evento não é duplicado para
aparecer em dois lugares, porque um fato gravado duas vezes deixa de ser um fato.
"""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalValue

PROPERTY_REGISTERED = "livestock.property_registered"
ANIMAL_REGISTERED = "livestock.animal_registered"
IDENTIFIER_ATTACHED = "livestock.identifier_attached"
IDENTIFIER_DEACTIVATED = "livestock.identifier_deactivated"
ANIMAL_MOVED = "livestock.animal_moved"
LOT_CREATED = "livestock.lot_created"
ANIMAL_ADDED_TO_LOT = "livestock.animal_added_to_lot"
ANIMAL_REMOVED_FROM_LOT = "livestock.animal_removed_from_lot"
VETERINARIAN_REGISTERED = "livestock.veterinarian_registered"
VETERINARIAN_STATUS_UPDATED = "livestock.veterinarian_status_updated"
MEDICATION_REGISTERED = "livestock.medication_registered"
MEDICATION_BATCH_REGISTERED = "livestock.medication_batch_registered"
PRESCRIPTION_ISSUED = "livestock.prescription_issued"
TREATMENT_APPLIED = "livestock.treatment_applied"
ANIMAL_EXITED = "livestock.animal_exited"

LIVESTOCK_EVENT_TYPES = frozenset(
    {
        PROPERTY_REGISTERED,
        ANIMAL_REGISTERED,
        IDENTIFIER_ATTACHED,
        IDENTIFIER_DEACTIVATED,
        ANIMAL_MOVED,
        LOT_CREATED,
        ANIMAL_ADDED_TO_LOT,
        ANIMAL_REMOVED_FROM_LOT,
        VETERINARIAN_REGISTERED,
        VETERINARIAN_STATUS_UPDATED,
        MEDICATION_REGISTERED,
        MEDICATION_BATCH_REGISTERED,
        PRESCRIPTION_ISSUED,
        TREATMENT_APPLIED,
        ANIMAL_EXITED,
    }
)

PAYLOAD_VERSION = 1


def _payload(event_type: str, value: Mapping[str, CanonicalValue]) -> CanonicalPayload:
    """Nome de schema derivado do event_type, para os dois nunca divergirem."""
    schema = f"{event_type.replace('.', '_')}_payload"
    return CanonicalPayload.from_mapping(schema=schema, version=PAYLOAD_VERSION, value=value)


def _id(value: TypedId) -> str:
    return str(value.value)


def _ids(values: tuple[TypedId, ...]) -> list[CanonicalValue]:
    """Ordem preservada: a ordem declarada pelo operador faz parte do fato."""
    return [_id(value) for value in values]


def _decimal(value: float | None) -> Decimal | None:
    """O serializador canônico recusa float; área vira Decimal pela via textual."""
    return None if value is None else Decimal(str(value))


def property_registered_payload(
    *,
    property_id: TypedId,
    code: str,
    name: str,
    municipality: str,
    state_code: str,
    registration_number: str | None,
    total_area_hectares: float | None,
) -> CanonicalPayload:
    return _payload(
        PROPERTY_REGISTERED,
        {
            "code": code,
            "municipality": municipality,
            "name": name,
            "property_id": _id(property_id),
            "registration_number": registration_number,
            "state_code": state_code,
            "total_area_hectares": _decimal(total_area_hectares),
        },
    )


def animal_registered_payload(
    *,
    animal_id: TypedId,
    birth_property_id: TypedId,
    sex: str,
    breed: str | None,
    birth_date: str | None,
) -> CanonicalPayload:
    return _payload(
        ANIMAL_REGISTERED,
        {
            "animal_id": _id(animal_id),
            "birth_date": birth_date,
            "birth_property_id": _id(birth_property_id),
            "breed": breed,
            "sex": sex,
        },
    )


def identifier_attached_payload(
    *,
    animal_id: TypedId,
    identifier_id: TypedId,
    identifier_type: str,
    identifier_value: str,
    attached_at: datetime,
) -> CanonicalPayload:
    return _payload(
        IDENTIFIER_ATTACHED,
        {
            "animal_id": _id(animal_id),
            "attached_at": attached_at,
            "identifier_id": _id(identifier_id),
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
        },
    )


def identifier_deactivated_payload(
    *,
    animal_id: TypedId,
    identifier_id: TypedId,
    deactivated_at: datetime,
) -> CanonicalPayload:
    return _payload(
        IDENTIFIER_DEACTIVATED,
        {
            "animal_id": _id(animal_id),
            "deactivated_at": deactivated_at,
            "identifier_id": _id(identifier_id),
        },
    )


def animal_moved_payload(
    *,
    movement_id: TypedId,
    origin_property_id: TypedId,
    destination_property_id: TypedId,
    movement_time: datetime,
    animal_ids: tuple[TypedId, ...],
    reason: str | None,
    evidence_reference: str | None,
) -> CanonicalPayload:
    return _payload(
        ANIMAL_MOVED,
        {
            "animal_ids": _ids(animal_ids),
            "destination_property_id": _id(destination_property_id),
            "evidence_reference": evidence_reference,
            "movement_id": _id(movement_id),
            "movement_time": movement_time,
            "origin_property_id": _id(origin_property_id),
            "reason": reason,
        },
    )


def lot_created_payload(
    *,
    lot_id: TypedId,
    property_id: TypedId,
    code: str,
    name: str,
    lot_type: str,
) -> CanonicalPayload:
    return _payload(
        LOT_CREATED,
        {
            "code": code,
            "lot_id": _id(lot_id),
            "lot_type": lot_type,
            "name": name,
            "property_id": _id(property_id),
        },
    )


def animal_added_to_lot_payload(
    *,
    lot_id: TypedId,
    animal_id: TypedId,
    membership_id: TypedId,
    valid_from: datetime,
) -> CanonicalPayload:
    return _payload(
        ANIMAL_ADDED_TO_LOT,
        {
            "animal_id": _id(animal_id),
            "lot_id": _id(lot_id),
            "membership_id": _id(membership_id),
            "valid_from": valid_from,
        },
    )


def animal_removed_from_lot_payload(
    *,
    lot_id: TypedId,
    animal_id: TypedId,
    membership_id: TypedId,
    valid_until: datetime,
) -> CanonicalPayload:
    return _payload(
        ANIMAL_REMOVED_FROM_LOT,
        {
            "animal_id": _id(animal_id),
            "lot_id": _id(lot_id),
            "membership_id": _id(membership_id),
            "valid_until": valid_until,
        },
    )


def veterinarian_registered_payload(
    *,
    veterinarian_id: TypedId,
    name: str,
    council_number: str,
    council_state: str,
    verification_status: str,
) -> CanonicalPayload:
    """O CPF fica de fora: identifica pessoa natural e não é necessário ao fato."""
    return _payload(
        VETERINARIAN_REGISTERED,
        {
            "council_number": council_number,
            "council_state": council_state,
            "name": name,
            "verification_status": verification_status,
            "veterinarian_id": _id(veterinarian_id),
        },
    )


def veterinarian_status_updated_payload(
    *,
    veterinarian_id: TypedId,
    old_status: str,
    new_status: str,
    evidence_reference: str | None,
) -> CanonicalPayload:
    return _payload(
        VETERINARIAN_STATUS_UPDATED,
        {
            "evidence_reference": evidence_reference,
            "new_status": new_status,
            "old_status": old_status,
            "veterinarian_id": _id(veterinarian_id),
        },
    )


def medication_registered_payload(
    *,
    medication_id: TypedId,
    trade_name: str,
    active_ingredient: str,
    manufacturer: str,
    withdrawal_period_days: int,
) -> CanonicalPayload:
    return _payload(
        MEDICATION_REGISTERED,
        {
            "active_ingredient": active_ingredient,
            "manufacturer": manufacturer,
            "medication_id": _id(medication_id),
            "trade_name": trade_name,
            "withdrawal_period_days": withdrawal_period_days,
        },
    )


def medication_batch_registered_payload(
    *,
    batch_id: TypedId,
    medication_id: TypedId,
    batch_number: str,
    expiry_date: datetime,
    manufacturing_date: datetime | None,
) -> CanonicalPayload:
    return _payload(
        MEDICATION_BATCH_REGISTERED,
        {
            "batch_id": _id(batch_id),
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "manufacturing_date": manufacturing_date,
            "medication_id": _id(medication_id),
        },
    )


def prescription_issued_payload(
    *,
    prescription_id: TypedId,
    veterinarian_id: TypedId,
    medication_id: TypedId,
    property_id: TypedId,
    prescribed_date: datetime,
    target_type: str,
    target_ids: tuple[TypedId, ...],
    dosage: str,
    administration_route: str,
    reason: str,
) -> CanonicalPayload:
    return _payload(
        PRESCRIPTION_ISSUED,
        {
            "administration_route": administration_route,
            "dosage": dosage,
            "medication_id": _id(medication_id),
            "prescribed_date": prescribed_date,
            "prescription_id": _id(prescription_id),
            "property_id": _id(property_id),
            "reason": reason,
            "target_ids": _ids(target_ids),
            "target_type": target_type,
            "veterinarian_id": _id(veterinarian_id),
        },
    )


def treatment_applied_payload(
    *,
    application_id: TypedId,
    animal_id: TypedId,
    medication_batch_id: TypedId,
    applied_at: datetime,
    dose: str | None,
    prescription_id: TypedId | None,
    evidence_references: tuple[UniversalReference, ...],
    evidence_notes: tuple[str, ...],
    corrects_application_id: TypedId | None,
) -> CanonicalPayload:
    return _payload(
        TREATMENT_APPLIED,
        {
            "animal_id": _id(animal_id),
            "application_id": _id(application_id),
            "applied_at": applied_at,
            "corrects_application_id": (
                None if corrects_application_id is None else _id(corrects_application_id)
            ),
            "dose": dose,
            "evidence_notes": list(evidence_notes),
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "medication_batch_id": _id(medication_batch_id),
            "prescription_id": None if prescription_id is None else _id(prescription_id),
        },
    )


def animal_exited_payload(
    *,
    exit_id: TypedId,
    animal_id: TypedId,
    exit_type: str,
    occurred_at: datetime,
    reason: str | None,
    destination: str | None,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    return _payload(
        ANIMAL_EXITED,
        {
            "animal_id": _id(animal_id),
            "destination": destination,
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "exit_id": _id(exit_id),
            "exit_type": exit_type,
            "occurred_at": occurred_at,
            "reason": reason,
        },
    )
