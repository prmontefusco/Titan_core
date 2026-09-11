"""Registro dos eventos da vertical no log append-only do Core (A4).

O Core é a fonte da verdade: a vertical não mantém log próprio nem numera
versões por conta própria. Ela monta o `DomainEvent` e entrega à porta
`DomainEventLog`, que é quem aplica o lock por agregado, confere a versão
esperada e encadeia o hash. Mesmo padrão de
`packages/livestock_application/event_recorder.py`.

`AssetOperationContext` existe porque `DomainEvent` exige autoria, origem e
correlação — e não o `OrganizationContext` inteiro do Core, que pressupõe
principal autenticado e membership. `from_organization_context` deixa essa
ponte pronta para quando `apps/api/asset/` existir (A5).
"""

from dataclasses import dataclass
from datetime import datetime

from packages.asset_domain.events import ASSET_EVENT_TYPES
from packages.core_application.event_log import DomainEventLog
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.core_domain.organization_context import OrganizationContext
from packages.shared_kernel import (
    Clock,
    OrganizationId,
    RecordTimestamps,
    TypedId,
    UniversalReference,
)

# Versão do contrato das referências de agregado emitidas pela vertical. Sobe
# quando a forma da referência mudar, nunca quando o payload mudar.
AGGREGATE_CONTRACT_VERSION = 1

EVENT_VERSION = 1


@dataclass(frozen=True, slots=True)
class AssetOperationContext:
    """Quem operou, por qual origem e sob qual correlação."""

    organization_id: OrganizationId
    actor_reference: UniversalReference
    source_reference: UniversalReference
    correlation_id: TypedId

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        for name, reference in (
            ("actor_reference", self.actor_reference),
            ("source_reference", self.source_reference),
        ):
            if not isinstance(reference, UniversalReference):
                raise TypeError(f"{name} deve ser UniversalReference.")
            if (
                reference.organization_id is not None
                and reference.organization_id != self.organization_id
            ):
                raise ValueError(f"{name} pertence a outra Organization.")
        if not isinstance(self.correlation_id, TypedId):
            raise TypeError("correlation_id deve ser TypedId.")
        if self.correlation_id.entity_type != "correlation":
            raise ValueError("correlation_id deve possuir tipo lógico 'correlation'.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        actor_id: TypedId,
        source_id: TypedId,
        correlation_id: TypedId | None = None,
    ) -> "AssetOperationContext":
        """Monta as referências a partir dos identificadores da operação.

        Sem `correlation_id`, cada operação vira sua própria correlação. Passar o
        mesmo valor em chamadas distintas é o que amarra um fluxo — abrir uma
        Work Order, reservar material, fechar — numa unidade rastreável.
        """
        return cls(
            organization_id=organization_id,
            actor_reference=UniversalReference(
                target_id=actor_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            ),
            source_reference=UniversalReference(
                target_id=source_id,
                organization_id=organization_id,
                contract_version=AGGREGATE_CONTRACT_VERSION,
            ),
            correlation_id=correlation_id or TypedId.new("correlation"),
        )

    @classmethod
    def from_organization_context(
        cls,
        context: OrganizationContext,
        *,
        source_id: TypedId,
        correlation_id: TypedId | None = None,
    ) -> "AssetOperationContext":
        """Ponte para quando a autoria vier de um principal autenticado (A5)."""
        if not isinstance(context, OrganizationContext):
            raise TypeError("context deve ser OrganizationContext.")
        return cls.create(
            organization_id=context.organization_id,
            actor_id=context.actor_id,
            source_id=source_id,
            correlation_id=correlation_id,
        )


@dataclass(frozen=True, slots=True)
class AssetEventRecorder:
    """Grava um evento da vertical no fluxo do agregado a que ele pertence."""

    event_log: DomainEventLog
    clock: Clock

    def record(
        self,
        *,
        context: AssetOperationContext,
        aggregate_id: TypedId,
        event_type: str,
        payload: CanonicalPayload,
        occurred_at: datetime,
        causation_id: TypedId | None = None,
    ) -> DomainEvent:
        if not isinstance(context, AssetOperationContext):
            raise TypeError("context deve ser AssetOperationContext.")
        if event_type not in ASSET_EVENT_TYPES:
            raise ValueError(
                f"'{event_type}' não é um evento declarado da vertical Asset. "
                "A guarda existe para o log do Core não receber tipo improvisado."
            )
        if not isinstance(payload, CanonicalPayload):
            raise TypeError("payload deve ser CanonicalPayload.")

        aggregate_reference = UniversalReference(
            target_id=aggregate_id,
            organization_id=context.organization_id,
            contract_version=AGGREGATE_CONTRACT_VERSION,
        )
        event = DomainEvent(
            event_id=TypedId.new("domain_event"),
            organization_id=context.organization_id,
            aggregate_reference=aggregate_reference,
            aggregate_version=self._next_version(aggregate_reference),
            event_type=event_type,
            event_version=EVENT_VERSION,
            timestamps=RecordTimestamps.capture(occurred_at=occurred_at, clock=self.clock),
            actor_reference=context.actor_reference,
            source_reference=context.source_reference,
            correlation_id=context.correlation_id,
            causation_id=causation_id,
            payload=payload,
        )
        self.event_log.append(event)
        return event

    def _next_version(self, aggregate_reference: UniversalReference) -> int:
        """A versão vem do log, não de um contador da vertical.

        O repositório do Core rejeita divergência (`EventAppendConflict`) sob lock
        do agregado, então uma corrida aqui vira erro de escrita e não um fluxo
        com buraco ou versão repetida.
        """
        versions = self.event_log.list_versions(aggregate_reference)
        return 1 if not versions else max(versions) + 1
