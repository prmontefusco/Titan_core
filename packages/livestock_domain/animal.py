"""Entidade de domínio Animal e AnimalIdentifier (Passo 8.2 - Titan Livestock)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class AnimalSex(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNKNOWN = "UNKNOWN"


class IdentifierType(StrEnum):
    OFFICIAL_SISBOV = "OFFICIAL_SISBOV"
    EAR_TAG = "EAR_TAG"
    RFID_CHIP = "RFID_CHIP"
    TATTOO = "TATTOO"
    OTHER = "OTHER"


class IdentifierState(StrEnum):
    ACTIVE = "ACTIVE"
    DEACTIVATED = "DEACTIVATED"


class VerificationStatus(StrEnum):
    DECLARADO = "DECLARADO"
    DOCUMENTADO = "DOCUMENTADO"
    VERIFICADO_EM_FONTE = "VERIFICADO_EM_FONTE"
    INDETERMINADO = "INDETERMINADO"


@dataclass(frozen=True, slots=True)
class AnimalIdentifier:
    identifier_id: TypedId
    identifier_type: IdentifierType
    identifier_value: str
    state: IdentifierState = IdentifierState.ACTIVE
    issuer_source: str | None = None
    evidence_reference: str | None = None
    verification_status: VerificationStatus = VerificationStatus.DECLARADO
    valid_from: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None
    attached_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deactivated_at: datetime | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from, field_name="valid_from")
        require_utc(self.attached_at, field_name="attached_at")
        if self.valid_until is not None:
            require_utc(self.valid_until, field_name="valid_until")
        if self.deactivated_at is not None:
            require_utc(self.deactivated_at, field_name="deactivated_at")
        if self.identifier_id.entity_type != "animal_identifier":
            raise ValueError(
                "identifier_id deve ter entity_type 'animal_identifier', recebido "
                f"'{self.identifier_id.entity_type}'."
            )
        if not self.identifier_value or not self.identifier_value.strip():
            raise ValueError("identifier_value não pode ser vazio.")
        if self.state == IdentifierState.DEACTIVATED and self.deactivated_at is None:
            raise ValueError(
                "deactivated_at deve ser informado quando o identificador for desativado."
            )


@dataclass(frozen=True, slots=True)
class Animal:
    animal_id: TypedId
    organization_id: OrganizationId
    birth_property_id: TypedId
    sex: AnimalSex
    breed: str | None = None
    birth_date: date | None = None
    identifiers: tuple[AnimalIdentifier, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{self.animal_id.entity_type}'."
            )
        if self.birth_property_id.entity_type != "rural_property":
            raise ValueError(
                "birth_property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.birth_property_id.entity_type}'."
            )

        # Valida que não há mais de uma tag ativa do mesmo tipo no mesmo animal
        active_types = set()
        for tag in self.identifiers:
            if tag.state == IdentifierState.ACTIVE:
                if tag.identifier_type in active_types:
                    raise ValueError(
                        f"Animal já possui um identificador ativo do tipo "
                        f"'{tag.identifier_type.value}'."
                    )
                active_types.add(tag.identifier_type)

    def attach_identifier(self, identifier: AnimalIdentifier) -> "Animal":
        if any(tag.identifier_id == identifier.identifier_id for tag in self.identifiers):
            raise ValueError(
                f"Identificador '{identifier.identifier_id.value}' já anexado ao animal."
            )

        new_identifiers = self.identifiers + (identifier,)
        return replace(self, identifiers=new_identifiers, version=self.version + 1)

    def deactivate_identifier(self, identifier_id: TypedId, deactivated_at: datetime) -> "Animal":
        updated_identifiers = []
        found = False
        for tag in self.identifiers:
            if tag.identifier_id == identifier_id:
                if tag.state == IdentifierState.DEACTIVATED:
                    raise ValueError(f"Identificador '{identifier_id.value}' já está desativado.")
                deactivated_tag = replace(
                    tag,
                    state=IdentifierState.DEACTIVATED,
                    valid_until=deactivated_at,
                    deactivated_at=deactivated_at,
                )
                updated_identifiers.append(deactivated_tag)
                found = True
            else:
                updated_identifiers.append(tag)

        if not found:
            raise KeyError(f"Identificador '{identifier_id.value}' não encontrado neste animal.")

        return replace(self, identifiers=tuple(updated_identifiers), version=self.version + 1)

    def get_active_identifier(self, identifier_type: IdentifierType) -> AnimalIdentifier | None:
        for tag in self.identifiers:
            if tag.identifier_type == identifier_type and tag.state == IdentifierState.ACTIVE:
                return tag
        return None
