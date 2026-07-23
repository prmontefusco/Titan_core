"""Casos de uso e porta de integração para Fatos da Vertical (ADR-0038/Passo 6.3)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.facts import FactSnapshot
from packages.shared_kernel import OrganizationId, TypedId


class FactProviderPort(Protocol):
    """Porta implementada pelas verticais (ex: Livestock) ou providers simulados."""

    def get_snapshot(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime,
    ) -> FactSnapshot: ...


@dataclass(frozen=True, slots=True)
class FactService:
    provider: FactProviderPort

    def get_snapshot_for_evaluation(
        self,
        organization_id: OrganizationId,
        target_id: TypedId,
        at_time: datetime,
    ) -> FactSnapshot:
        return self.provider.get_snapshot(
            organization_id=organization_id, target_id=target_id, at_time=at_time
        )
