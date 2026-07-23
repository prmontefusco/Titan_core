"""Entidade de domínio RuralProperty (Passo 8.1 - Titan Livestock)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


@dataclass(frozen=True, slots=True)
class RuralProperty:
    property_id: TypedId
    organization_id: OrganizationId
    code: str
    name: str
    municipality: str
    state_code: str
    registration_number: str | None = None
    total_area_hectares: float | None = None
    status: str = "ACTIVE"
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.property_id.entity_type != "rural_property":
            raise ValueError(
                "property_id deve ter entity_type 'rural_property', recebido "
                f"'{self.property_id.entity_type}'."
            )
        if not self.code or not self.code.strip():
            raise ValueError("code da propriedade rural não pode ser vazio.")
        if not self.name or not self.name.strip():
            raise ValueError("name da propriedade rural não pode ser vazio.")
        if not self.municipality or not self.municipality.strip():
            raise ValueError("municipality da propriedade rural não pode ser vazio.")
        state = self.state_code.strip() if self.state_code else ""
        if len(state) != 2 or not state.isupper():
            raise ValueError("state_code deve conter exatamente 2 letras maiúsculas (ex: 'SP').")
        if self.total_area_hectares is not None and self.total_area_hectares <= 0:
            raise ValueError(
                "total_area_hectares, quando informado, deve ser um valor positivo (> 0)."
            )
