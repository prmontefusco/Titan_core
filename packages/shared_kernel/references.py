"""Referências universais entre capacidades do Titan."""

from dataclasses import dataclass

from packages.shared_kernel.identifiers import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class UniversalReference:
    """Referência estável sem expor detalhes de persistência ou da vertical."""

    target_id: TypedId
    organization_id: OrganizationId | None
    contract_version: int

    def __post_init__(self) -> None:
        if not isinstance(self.target_id, TypedId):
            raise TypeError("target_id deve ser um TypedId.")
        if self.organization_id is not None and not isinstance(
            self.organization_id, OrganizationId
        ):
            raise TypeError("organization_id deve ser um OrganizationId ou None.")
        if isinstance(self.contract_version, bool) or not isinstance(self.contract_version, int):
            raise TypeError("contract_version deve ser um número inteiro.")
        if self.contract_version < 1:
            raise ValueError("contract_version deve ser maior ou igual a 1.")
