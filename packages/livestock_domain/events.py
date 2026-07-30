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
SANITARY_CAMPAIGN_REGISTERED = "livestock.sanitary_campaign_registered"
PRESCRIPTION_ISSUED = "livestock.prescription_issued"
TREATMENT_APPLIED = "livestock.treatment_applied"
ANIMAL_EXITED = "livestock.animal_exited"
EXTERNAL_COUNTERPARTY_REGISTERED = "livestock.external_counterparty_registered"
ESTABLISHMENT_QUALIFICATION_RECORDED = "livestock.establishment_qualification_recorded"
TRANSFER_ARTIFACT_RECEIVED = "livestock.transfer_artifact_received"
IMPORTED_FACT_RECORDED = "livestock.imported_fact_recorded"
PARENTAGE_REGISTERED = "livestock.parentage_registered"
REPRODUCTIVE_EVENT_RECORDED = "livestock.reproductive_event_recorded"
PROPERTY_GEOMETRY_RECORDED = "livestock.property_geometry_recorded"
PROPERTY_ENVIRONMENTAL_EMBARGO_ASSERTION_RECORDED = (
    "livestock.property_environmental_embargo_assertion_recorded"
)
TRANSFORMATION_EVENT_RECORDED = "livestock.transformation_event_recorded"

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
        SANITARY_CAMPAIGN_REGISTERED,
        PRESCRIPTION_ISSUED,
        TREATMENT_APPLIED,
        ANIMAL_EXITED,
        EXTERNAL_COUNTERPARTY_REGISTERED,
        ESTABLISHMENT_QUALIFICATION_RECORDED,
        IMPORTED_FACT_RECORDED,
        TRANSFER_ARTIFACT_RECEIVED,
        PARENTAGE_REGISTERED,
        REPRODUCTIVE_EVENT_RECORDED,
        PROPERTY_GEOMETRY_RECORDED,
        PROPERTY_ENVIRONMENTAL_EMBARGO_ASSERTION_RECORDED,
        TRANSFORMATION_EVENT_RECORDED,
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
    birth_property_id: TypedId | None,
    sex: str,
    breed: str | None,
    birth_date: str | None,
) -> CanonicalPayload:
    """`birth_property_id` é nulo quando o parto não teve propriedade determinável.

    Ausência de dado contextual não impede o registro do fato (ADR-0040), e o
    payload precisa poder dizer "não se sabe" em vez de inventar uma fazenda.
    """
    return _payload(
        ANIMAL_REGISTERED,
        {
            "animal_id": _id(animal_id),
            "birth_date": birth_date,
            "birth_property_id": None if birth_property_id is None else _id(birth_property_id),
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
    product_class: str,
) -> CanonicalPayload:
    return _payload(
        MEDICATION_REGISTERED,
        {
            "active_ingredient": active_ingredient,
            "manufacturer": manufacturer,
            "medication_id": _id(medication_id),
            "product_class": product_class,
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


def sanitary_campaign_registered_payload(
    *,
    campaign_id: TypedId,
    code: str,
    name: str,
    starts_at: datetime,
    ends_at: datetime,
    disease: str | None,
    authority: str | None,
) -> CanonicalPayload:
    return _payload(
        SANITARY_CAMPAIGN_REGISTERED,
        {
            "authority": authority,
            "campaign_id": _id(campaign_id),
            "code": code,
            "disease": disease,
            "ends_at": ends_at,
            "name": name,
            "starts_at": starts_at,
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
    sanitary_campaign_id: TypedId | None,
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
            "sanitary_campaign_id": (
                None if sanitary_campaign_id is None else _id(sanitary_campaign_id)
            ),
        },
    )


def property_geometry_recorded_payload(
    *,
    geometry_id: TypedId,
    property_id: TypedId,
    source: str,
    srid: int,
    source_digest: str,
    external_reference: str | None,
    version: int,
    captured_at: datetime | None,
) -> CanonicalPayload:
    """O agregado é a geometria, e a propriedade a cita.

    **O polígono não entra no payload — só o digest dele.** O evento diz que a
    geometria foi registrada, de qual fonte e com que impressão digital; o
    material fica na tabela, sob RLS. Copiá-lo para o log faria a coordenada
    protegida existir em dois lugares com controles de acesso diferentes.
    """
    return _payload(
        PROPERTY_GEOMETRY_RECORDED,
        {
            "captured_at": captured_at,
            "external_reference": external_reference,
            "geometry_id": _id(geometry_id),
            "property_id": _id(property_id),
            "source": source,
            "source_digest": source_digest,
            "srid": srid,
            "version": version,
        },
    )


def reproductive_event_recorded_payload(
    *,
    event_id: TypedId,
    dam_id: TypedId,
    sire_id: TypedId | None,
    event_type: str,
    occurred_at: datetime,
    offspring: tuple[tuple[TypedId, str], ...],
    gestational_age_days: int | None,
    gestational_age_basis: str,
    notes: str | None,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    """O agregado é o próprio evento reprodutivo, e não a mãe nem a cria.

    É a entidade criada pela operação, e as duas pontas a citam — a linha do
    tempo da mãe contém o parto, e a do bezerro começa nele. Emitir um evento
    para cada ponta transformaria um fato em dois.

    A classificação do aborto em precoce ou tardio **não** entra aqui: ela é
    derivada por regra versionada, e gravá-la criaria segunda fonte de verdade.
    """
    return _payload(
        REPRODUCTIVE_EVENT_RECORDED,
        {
            "dam_id": _id(dam_id),
            "event_id": _id(event_id),
            "event_type": event_type,
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "gestational_age_basis": gestational_age_basis,
            "gestational_age_days": gestational_age_days,
            "notes": notes,
            "occurred_at": occurred_at,
            "offspring": [
                {"animal_id": _id(animal_id), "outcome": outcome}
                for animal_id, outcome in offspring
            ],
            "sire_id": None if sire_id is None else _id(sire_id),
        },
    )


def parentage_registered_payload(
    *,
    relation_id: TypedId,
    offspring_id: TypedId,
    parent_id: TypedId,
    role: str,
    relation_type: str,
    confidence: str,
    confidence_reason: str,
    occurred_at: datetime,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    """O agregado deste evento é a **relação**, não a cria nem o progenitor.

    É o vínculo que nasce aqui, e é ele que as duas pontas enxergam por citação —
    do mesmo modo que a movimentação pertence ao `animal_movement` e aparece na
    linha do tempo de cada animal citado. Emiti-lo duas vezes, uma para cada
    ponta, transformaria um fato em dois.
    """
    return _payload(
        PARENTAGE_REGISTERED,
        {
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "occurred_at": occurred_at,
            "offspring_id": _id(offspring_id),
            "parent_id": _id(parent_id),
            "relation_id": _id(relation_id),
            "relation_type": relation_type,
            "role": role,
        },
    )


def transformation_event_recorded_payload(
    *,
    event_id: TypedId,
    process_type: str,
    occurred_at: datetime,
    facility_id: TypedId,
    input_subject_ids: tuple[TypedId, ...],
    output_items: tuple[tuple[TypedId, str], ...],
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    """O agregado é a própria transformação — nunca o animal nem os itens criados.

    Mesma razão do parto e do parentesco: é a entidade nascida aqui, e é ela que
    as pontas (animal consumido, itens produzidos) passam a citar por referência.
    """
    return _payload(
        TRANSFORMATION_EVENT_RECORDED,
        {
            "event_id": _id(event_id),
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "facility_id": _id(facility_id),
            "input_subject_ids": _ids(input_subject_ids),
            "occurred_at": occurred_at,
            "output_items": [
                {"item_id": _id(item_id), "item_type": item_type}
                for item_id, item_type in output_items
            ],
            "process_type": process_type,
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
    destination_counterparty_id: TypedId | None,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    return _payload(
        ANIMAL_EXITED,
        {
            "animal_id": _id(animal_id),
            "destination": destination,
            "destination_counterparty_id": (
                None if destination_counterparty_id is None else _id(destination_counterparty_id)
            ),
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "exit_id": _id(exit_id),
            "exit_type": exit_type,
            "occurred_at": occurred_at,
            "reason": reason,
        },
    )


def external_counterparty_registered_payload(
    *,
    counterparty_id: TypedId,
    name: str,
    counterparty_type: str,
    identifiers: tuple[str, ...],
    notes: str | None,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    return _payload(
        EXTERNAL_COUNTERPARTY_REGISTERED,
        {
            "counterparty_id": _id(counterparty_id),
            "counterparty_type": counterparty_type,
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "identifiers": list(identifiers),
            "name": name,
            "notes": notes,
        },
    )


def establishment_qualification_recorded_payload(
    *,
    qualification_id: TypedId,
    counterparty_id: TypedId,
    market_purpose: str,
    status: str,
    source_name: str,
    source_version: str | None,
    assessed_at: datetime,
    evidence_references: tuple[UniversalReference, ...],
) -> CanonicalPayload:
    return _payload(
        ESTABLISHMENT_QUALIFICATION_RECORDED,
        {
            "assessed_at": assessed_at,
            "counterparty_id": _id(counterparty_id),
            "evidence_references": [_id(r.target_id) for r in evidence_references],
            "market_purpose": market_purpose,
            "qualification_id": _id(qualification_id),
            "source_name": source_name,
            "source_version": source_version,
            "status": status,
        },
    )


def transfer_artifact_received_payload(
    *,
    artifact_id: TypedId,
    animal_id: TypedId,
    source_counterparty_id: TypedId,
    bundle_digest: str,
    bundle_issued_at: datetime,
    transfer_effective_at: datetime,
    coverage_known_from: datetime | None,
    coverage_known_until: datetime | None,
    gap_codes: tuple[str, ...],
    issuer_name: str | None,
) -> CanonicalPayload:
    return _payload(
        TRANSFER_ARTIFACT_RECEIVED,
        {
            "animal_id": _id(animal_id),
            "artifact_id": _id(artifact_id),
            "bundle_digest": bundle_digest,
            "bundle_issued_at": bundle_issued_at,
            "coverage_known_from": coverage_known_from,
            "coverage_known_until": coverage_known_until,
            "gap_codes": list(gap_codes),
            "issuer_name": issuer_name,
            "source_counterparty_id": _id(source_counterparty_id),
            "transfer_effective_at": transfer_effective_at,
        },
    )


def imported_fact_recorded_payload(
    *,
    imported_fact_id: TypedId,
    animal_id: TypedId,
    source_artifact_id: TypedId,
    fact_type: str,
    occurred_at: datetime,
    asserted_by: str,
    received_by: TypedId,
    origin: str,
    confidence_tier: str,
) -> CanonicalPayload:
    return _payload(
        IMPORTED_FACT_RECORDED,
        {
            "animal_id": _id(animal_id),
            "asserted_by": asserted_by,
            "confidence_tier": confidence_tier,
            "fact_type": fact_type,
            "imported_fact_id": _id(imported_fact_id),
            "occurred_at": occurred_at,
            "origin": origin,
            "received_by": _id(received_by),
            "source_artifact_id": _id(source_artifact_id),
        },
    )


def property_environmental_embargo_assertion_recorded_payload(
    *,
    assertion_id: TypedId,
    property_id: TypedId,
    geometry_id: TypedId | None,
    geometry_version: int | None,
    source_name: str,
    source_layer: str,
    operation: str,
    status: str,
    source_digest: str | None,
    response_digest: str | None,
    version_ids: tuple[str, ...],
    restriction_count: int,
    observed_at: datetime,
) -> CanonicalPayload:
    return _payload(
        PROPERTY_ENVIRONMENTAL_EMBARGO_ASSERTION_RECORDED,
        {
            "assertion_id": _id(assertion_id),
            "geometry_id": None if geometry_id is None else _id(geometry_id),
            "geometry_version": geometry_version,
            "observed_at": observed_at,
            "operation": operation,
            "property_id": _id(property_id),
            "response_digest": response_digest,
            "restriction_count": restriction_count,
            "source_digest": source_digest,
            "source_layer": source_layer,
            "source_name": source_name,
            "status": status,
            "version_ids": list(version_ids),
        },
    )
