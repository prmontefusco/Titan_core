"""Contraparte externa local da vertical Livestock (ADR-0042)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc


class CounterpartyType(StrEnum):
    FARM = "FARM"
    SLAUGHTERHOUSE = "SLAUGHTERHOUSE"
    TRADER = "TRADER"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ExternalCounterparty:
    """Representacao local que uma Organization mantem sobre um terceiro."""

    counterparty_id: TypedId
    organization_id: OrganizationId
    name: str
    counterparty_type: CounterpartyType
    identifiers: tuple[str, ...] = ()
    evidence_references: tuple[UniversalReference, ...] = ()
    notes: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.counterparty_id.entity_type != "external_counterparty":
            raise ValueError(
                "counterparty_id deve ter entity_type 'external_counterparty', recebido "
                f"'{self.counterparty_id.entity_type}'."
            )
        if not self.name.strip():
            raise ValueError("name nao pode ser vazio.")
        if not isinstance(self.counterparty_type, CounterpartyType):
            raise TypeError("counterparty_type deve ser um CounterpartyType.")
        for identifier in self.identifiers:
            if not identifier.strip():
                raise ValueError("identifiers nao pode conter valor vazio.")
        if self.notes is not None and not self.notes.strip():
            raise ValueError("notes, quando informado, nao pode ser vazio.")
        for reference in self.evidence_references:
            if not isinstance(reference, UniversalReference):
                raise TypeError("evidence_references deve conter UniversalReference.")
            if reference.target_id.entity_type != "evidence":
                raise ValueError("evidence_references deve apontar para 'evidence'.")
            if reference.organization_id != self.organization_id:
                raise ValueError("A evidencia citada pertence a outra Organization.")
