"""Modelo de domínio imutável para Relação Universal e Temporal (Passo 7.1)."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier, ValidityPeriod
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

# O tipo da relação é um nome canônico livre, não um enum: o Core não conhece os
# vínculos de nenhuma vertical. Restringi-lo a um conjunto fechado obrigaria o
# Core a mudar sempre que uma vertical precisasse de um vínculo novo.
_RELATION_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


@dataclass(frozen=True, slots=True)
class UniversalRelation:
    """Relação genérica, temporal e auditável entre dois Subjects.

    Registra origem, destino, tipo, período de validade, Organization responsável,
    Event criador, Evidences que sustentam o vínculo, confiança e quantidade
    opcional. Não concede acesso entre Organizations.
    """

    relation_id: TypedId
    organization_id: OrganizationId
    source_reference: UniversalReference
    target_reference: UniversalReference
    relation_type: str
    period: ValidityPeriod
    created_at: datetime
    confidence: ConfidenceLevel
    created_by_event: TypedId | None = None
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    quantity: Decimal | None = None
    unit: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    metadata_version: int = 1

    def __post_init__(self) -> None:
        if self.relation_id.entity_type != "relation":
            raise ValueError("relation_id deve ser do tipo 'relation'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.source_reference, UniversalReference):
            raise TypeError("source_reference deve ser uma UniversalReference.")
        if not isinstance(self.target_reference, UniversalReference):
            raise TypeError("target_reference deve ser uma UniversalReference.")
        if not isinstance(self.relation_type, str) or not _RELATION_TYPE_PATTERN.fullmatch(
            self.relation_type
        ):
            raise ValueError("relation_type deve usar nome canônico em minúsculas.")
        if not isinstance(self.period, ValidityPeriod):
            raise TypeError("period deve ser um ValidityPeriod.")
        if not isinstance(self.confidence, ConfidenceLevel):
            raise TypeError("confidence deve ser um ConfidenceLevel.")
        if (
            self.created_by_event is not None
            and self.created_by_event.entity_type != "domain_event"
        ):
            raise ValueError("created_by_event deve ser do tipo 'domain_event'.")
        if not isinstance(self.evidence_references, tuple):
            raise TypeError("evidence_references deve ser uma tupla.")
        if isinstance(self.quantity, float):
            raise TypeError("quantity não aceita float; utilize Decimal.")
        if self.quantity is not None and not isinstance(self.quantity, Decimal):
            raise TypeError("quantity deve ser um Decimal ou None.")
        if self.quantity is not None and self.quantity < 0:
            raise ValueError("quantity não pode ser negativa.")
        if self.quantity is not None and not self.unit.strip():
            raise ValueError("Toda quantidade exige unidade declarada.")
        if not isinstance(self.metadata_version, int) or self.metadata_version < 1:
            raise ValueError("metadata_version deve ser um número inteiro >= 1.")

        # A relação vive dentro de uma Organization: uma ponta em outra Organization
        # transformaria a genealogia em caminho de vazamento entre tenants.
        for label, reference in (
            ("origem", self.source_reference),
            ("destino", self.target_reference),
        ):
            if (
                reference.organization_id is not None
                and reference.organization_id != self.organization_id
            ):
                raise ValueError(
                    f"A {label} da relação pertence a outra Organization: "
                    "relação universal não concede acesso entre Organizations."
                )

        if (
            self.source_reference.target_id == self.target_reference.target_id
            and self.relation_type != "supersession"
        ):
            raise ValueError("Uma relação não pode ligar um Subject a ele mesmo.")

    def is_valid_at(self, instant: datetime) -> bool:
        return self.period.is_valid_at(instant)

    def close(self, ended_at: datetime) -> "UniversalRelation":
        """Encerra a vigência da relação preservando todo o histórico.

        O vínculo não é apagado: passa a ter fim declarado, e continua respondendo
        consultas em instantes anteriores ao encerramento.
        """
        if self.period.valid_until is not None:
            raise ValueError("A relação já possui fim de vigência declarado.")
        if self.period.valid_from is not None and ended_at < self.period.valid_from:
            raise ValueError("O encerramento não pode ser anterior ao início da vigência.")
        return UniversalRelation(
            relation_id=self.relation_id,
            organization_id=self.organization_id,
            source_reference=self.source_reference,
            target_reference=self.target_reference,
            relation_type=self.relation_type,
            period=ValidityPeriod(valid_from=self.period.valid_from, valid_until=ended_at),
            created_at=self.created_at,
            confidence=self.confidence,
            created_by_event=self.created_by_event,
            evidence_references=self.evidence_references,
            quantity=self.quantity,
            unit=self.unit,
            metadata=dict(self.metadata),
            metadata_version=self.metadata_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": str(self.relation_id.value),
            "organization_id": str(self.organization_id.value),
            "source_reference": reference_to_dict(self.source_reference),
            "target_reference": reference_to_dict(self.target_reference),
            "relation_type": self.relation_type,
            "valid_from": (self.period.valid_from.isoformat() if self.period.valid_from else None),
            "valid_until": (
                self.period.valid_until.isoformat() if self.period.valid_until else None
            ),
            "created_at": self.created_at.isoformat(),
            "confidence_tier": self.confidence.tier.value,
            "confidence_reason": self.confidence.reason,
            "created_by_event": (
                str(self.created_by_event.value) if self.created_by_event else None
            ),
            "evidence_references": [reference_to_dict(r) for r in self.evidence_references],
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "unit": self.unit,
            "metadata": self.metadata,
            "metadata_version": self.metadata_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "UniversalRelation":
        source = reference_from_dict(data["source_reference"])
        target = reference_from_dict(data["target_reference"])
        if source is None or target is None:
            raise ValueError("Relação exige origem e destino.")
        raw_event = data.get("created_by_event")
        raw_quantity = data.get("quantity")
        return cls(
            relation_id=TypedId(entity_type="relation", value=UUID(data["relation_id"])),
            organization_id=OrganizationId(UUID(data["organization_id"])),
            source_reference=source,
            target_reference=target,
            relation_type=data["relation_type"],
            period=ValidityPeriod(
                valid_from=(
                    datetime.fromisoformat(data["valid_from"]) if data.get("valid_from") else None
                ),
                valid_until=(
                    datetime.fromisoformat(data["valid_until"]) if data.get("valid_until") else None
                ),
            ),
            created_at=datetime.fromisoformat(data["created_at"]),
            confidence=ConfidenceLevel(
                tier=ConfidenceTier(data["confidence_tier"]),
                reason=data["confidence_reason"],
            ),
            created_by_event=(
                TypedId(entity_type="domain_event", value=UUID(raw_event))
                if raw_event is not None
                else None
            ),
            evidence_references=tuple(
                ref
                for ref in (reference_from_dict(i) for i in data.get("evidence_references", []))
                if ref is not None
            ),
            quantity=Decimal(raw_quantity) if raw_quantity is not None else None,
            unit=data.get("unit", ""),
            metadata=dict(data.get("metadata", {})),
            metadata_version=data.get("metadata_version", 1),
        )

    @classmethod
    def create(
        cls,
        organization_id: OrganizationId,
        source_reference: UniversalReference,
        target_reference: UniversalReference,
        relation_type: str,
        created_at: datetime,
        confidence: ConfidenceLevel,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        created_by_event: TypedId | None = None,
        evidence_references: tuple[UniversalReference, ...] = (),
        quantity: Decimal | None = None,
        unit: str = "",
        metadata: dict[str, Any] | None = None,
        metadata_version: int = 1,
    ) -> "UniversalRelation":
        return cls(
            relation_id=TypedId.new("relation"),
            organization_id=organization_id,
            source_reference=source_reference,
            target_reference=target_reference,
            relation_type=relation_type.strip().lower(),
            period=ValidityPeriod(valid_from=valid_from, valid_until=valid_until),
            created_at=created_at,
            confidence=confidence,
            created_by_event=created_by_event,
            evidence_references=evidence_references,
            quantity=quantity,
            unit=unit.strip(),
            metadata=dict(metadata or {}),
            metadata_version=metadata_version,
        )
