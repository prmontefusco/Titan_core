"""Entitlement de SLI como decisao governada do Core.

Este modulo nao implementa regra de cobertura contratual. Ele define a fronteira
de aplicacao do Asset para solicitar uma decisao ao Core e registrar o resultado
que comandos de WorkOrder consomem (I-SLI-4/5).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import (
    SUSTAINMENT_ENTITLEMENT_RESOLVED,
    sustainment_entitlement_resolved_payload,
)
from packages.shared_kernel import TypedId


class EntitlementOutcome(StrEnum):
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    GRANTED_WITH_EXCEPTION = "GRANTED_WITH_EXCEPTION"


class EntitlementDecisionInvalida(ValueError):
    """A porta de decisao retornou material incompatível com o comando."""


@dataclass(frozen=True, slots=True)
class EntitlementRequest:
    vehicle_ref: TypedId
    subject_ref: TypedId
    contract_ref: TypedId
    contract_version_no: int
    instant: datetime
    quantity: str


@dataclass(frozen=True, slots=True)
class EntitlementResolution:
    vehicle_ref: TypedId
    subject_ref: TypedId
    instant: datetime
    decision_ref: TypedId
    outcome: EntitlementOutcome
    breakdown: str


class EntitlementDecisionPort(Protocol):
    def resolve(self, request: EntitlementRequest) -> EntitlementResolution: ...


class EntitlementExceptionDecisionPort(Protocol):
    def authorize_exception(
        self,
        *,
        denied_resolution: EntitlementResolution,
        reason: str,
        decided_at: datetime,
    ) -> EntitlementResolution: ...


def _validate_resolution(
    request: EntitlementRequest,
    resolution: EntitlementResolution,
) -> None:
    _validate_resolution_fields(
        expected_vehicle_ref=request.vehicle_ref,
        expected_subject_ref=request.subject_ref,
        expected_instant=request.instant,
        resolution=resolution,
    )


def _validate_resolution_fields(
    *,
    expected_vehicle_ref: TypedId,
    expected_subject_ref: TypedId,
    expected_instant: datetime,
    resolution: EntitlementResolution,
) -> None:
    if resolution.vehicle_ref != expected_vehicle_ref:
        raise EntitlementDecisionInvalida("Decision de entitlement diverge do vehicle_ref.")
    if resolution.subject_ref != expected_subject_ref:
        raise EntitlementDecisionInvalida("Decision de entitlement diverge do subject_ref.")
    if resolution.instant != expected_instant:
        raise EntitlementDecisionInvalida("Decision de entitlement diverge do instante avaliado.")
    if not resolution.breakdown.strip():
        raise EntitlementDecisionInvalida("Decision de entitlement exige breakdown explicavel.")


@dataclass(frozen=True, slots=True)
class EntitlementService:
    decision_port: EntitlementDecisionPort
    exception_decision_port: EntitlementExceptionDecisionPort
    recorder: AssetEventRecorder

    def resolve_entitlement(
        self,
        context: AssetOperationContext,
        request: EntitlementRequest,
        *,
        occurred_at: datetime,
    ) -> EntitlementResolution:
        resolution = self.decision_port.resolve(request)
        _validate_resolution(request, resolution)
        self.recorder.record(
            context=context,
            aggregate_id=request.vehicle_ref,
            event_type=SUSTAINMENT_ENTITLEMENT_RESOLVED,
            payload=sustainment_entitlement_resolved_payload(
                vehicle_ref=resolution.vehicle_ref,
                subject_ref=resolution.subject_ref,
                instant=resolution.instant,
                decision_ref=resolution.decision_ref,
                outcome=resolution.outcome.value,
                breakdown=resolution.breakdown,
            ),
            occurred_at=occurred_at,
        )
        return resolution

    def authorize_entitlement_exception(
        self,
        context: AssetOperationContext,
        denied_resolution: EntitlementResolution,
        *,
        reason: str,
        occurred_at: datetime,
    ) -> EntitlementResolution:
        if denied_resolution.outcome is not EntitlementOutcome.DENIED:
            raise EntitlementDecisionInvalida(
                "Excecao de entitlement exige uma decision original DENIED."
            )
        if not reason.strip():
            raise EntitlementDecisionInvalida("Excecao de entitlement exige motivo.")
        resolution = self.exception_decision_port.authorize_exception(
            denied_resolution=denied_resolution,
            reason=reason,
            decided_at=occurred_at,
        )
        if resolution.outcome is not EntitlementOutcome.GRANTED_WITH_EXCEPTION:
            raise EntitlementDecisionInvalida(
                "Excecao autorizada deve retornar GRANTED_WITH_EXCEPTION."
            )
        _validate_resolution_fields(
            expected_vehicle_ref=denied_resolution.vehicle_ref,
            expected_subject_ref=denied_resolution.subject_ref,
            expected_instant=denied_resolution.instant,
            resolution=resolution,
        )
        self.recorder.record(
            context=context,
            aggregate_id=resolution.vehicle_ref,
            event_type=SUSTAINMENT_ENTITLEMENT_RESOLVED,
            payload=sustainment_entitlement_resolved_payload(
                vehicle_ref=resolution.vehicle_ref,
                subject_ref=resolution.subject_ref,
                instant=resolution.instant,
                decision_ref=resolution.decision_ref,
                outcome=resolution.outcome.value,
                breakdown=resolution.breakdown,
            ),
            occurred_at=occurred_at,
        )
        return resolution
