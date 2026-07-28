"""Testes de domínio para TransformationEvent e TraceableItem (ADR-0046, Passo 11.2)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from packages.livestock_domain.transformation import (
    BalanceResult,
    BalanceStatus,
    ConsumptionMode,
    ParticipantRole,
    ProcessType,
    TraceableItem,
    TraceableItemType,
    TransformationBalance,
    TransformationEvent,
    TransformationParticipant,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

MOMENTO = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _org() -> OrganizationId:
    return OrganizationId(uuid4())


def _reference(organization_id: OrganizationId, entity_type: str) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=organization_id, contract_version=1
    )


def _input(organization_id: OrganizationId, **overrides: Any) -> TransformationParticipant:
    defaults: dict[str, Any] = dict(
        subject_reference=_reference(organization_id, "animal"),
        role=ParticipantRole.INPUT,
        consumption_mode=ConsumptionMode.FULL,
    )
    defaults.update(overrides)
    return TransformationParticipant(**defaults)


def _output(organization_id: OrganizationId, **overrides: Any) -> TransformationParticipant:
    defaults: dict[str, Any] = dict(
        subject_reference=_reference(organization_id, "traceable_item"),
        role=ParticipantRole.OUTPUT,
        quantity=Decimal("100"),
        unit="kg",
    )
    defaults.update(overrides)
    return TransformationParticipant(**defaults)


def _event(organization_id: OrganizationId, **overrides: Any) -> TransformationEvent:
    defaults: dict[str, Any] = dict(
        event_id=TypedId.new("transformation_event"),
        organization_id=organization_id,
        process_type=ProcessType.SLAUGHTER,
        occurred_at=MOMENTO,
        facility_reference=_reference(organization_id, "rural_property"),
        inputs=(_input(organization_id),),
        outputs=(_output(organization_id), _output(organization_id)),
        created_at=MOMENTO,
    )
    defaults.update(overrides)
    return TransformationEvent(**defaults)


class TestTransformationParticipant:
    def test_output_nao_aceita_consumption_mode(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="consumption_mode não se aplica a OUTPUT"):
            _output(org, consumption_mode=ConsumptionMode.FULL)

    def test_quantidade_exige_unidade(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="unidade declarada"):
            _output(org, unit="")

    def test_quantidade_nao_aceita_float(self) -> None:
        org = _org()
        with pytest.raises(TypeError, match="Decimal"):
            _output(org, quantity=1.5)

    def test_quantidade_negativa_e_recusada(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="negativa"):
            _output(org, quantity=Decimal("-1"))


class TestTraceableItem:
    def test_exige_entity_type_correto(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="traceable_item"):
            TraceableItem(
                item_id=TypedId.new("animal"),
                organization_id=org,
                item_type=TraceableItemType.HALF_CARCASS,
                created_by_transformation_id=None,
                created_at=MOMENTO,
            )

    def test_created_by_transformation_id_exige_tipo_correto(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="transformation_event"):
            TraceableItem(
                item_id=TypedId.new("traceable_item"),
                organization_id=org,
                item_type=TraceableItemType.HALF_CARCASS,
                created_by_transformation_id=TypedId.new("animal"),
                created_at=MOMENTO,
            )

    def test_label_vazio_e_recusado(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="não pode ser vazio"):
            TraceableItem(
                item_id=TypedId.new("traceable_item"),
                organization_id=org,
                item_type=TraceableItemType.HALF_CARCASS,
                created_by_transformation_id=None,
                created_at=MOMENTO,
                label="   ",
            )


class TestTransformationEvent:
    def test_cria_evento_valido_com_fan_out(self) -> None:
        org = _org()
        evento = _event(org)
        assert len(evento.inputs) == 1
        assert len(evento.outputs) == 2

    def test_exige_ao_menos_uma_entrada(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="ao menos uma entrada"):
            _event(org, inputs=())

    def test_exige_ao_menos_uma_saida(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="ao menos uma saída"):
            _event(org, outputs=())

    def test_inputs_recusa_participante_com_role_output(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="role=INPUT"):
            _event(org, inputs=(_output(org),))

    def test_outputs_recusa_participante_com_role_input(self) -> None:
        org = _org()
        with pytest.raises(ValueError, match="role=OUTPUT"):
            _event(org, outputs=(_input(org),))

    def test_sujeito_nao_pode_ser_input_e_output_do_mesmo_evento(self) -> None:
        org = _org()
        compartilhado = _reference(org, "animal")
        with pytest.raises(ValueError, match="input e output do mesmo"):
            _event(
                org,
                inputs=(
                    TransformationParticipant(
                        subject_reference=compartilhado,
                        role=ParticipantRole.INPUT,
                        consumption_mode=ConsumptionMode.FULL,
                    ),
                ),
                outputs=(
                    TransformationParticipant(
                        subject_reference=compartilhado,
                        role=ParticipantRole.OUTPUT,
                        quantity=Decimal("1"),
                        unit="kg",
                    ),
                    _output(org),
                ),
            )

    def test_facility_de_outra_organizacao_e_recusada(self) -> None:
        org = _org()
        outra = _org()
        with pytest.raises(ValueError, match="outra Organization"):
            _event(org, facility_reference=_reference(outra, "rural_property"))

    def test_subject_reference_de_outra_organizacao_e_recusada(self) -> None:
        org = _org()
        outra = _org()
        with pytest.raises(ValueError, match="outra Organization"):
            _event(org, inputs=(_input(outra),))

    def test_evidence_reference_de_outra_organizacao_e_recusada(self) -> None:
        org = _org()
        outra = _org()
        with pytest.raises(ValueError, match="outra Organization"):
            _event(org, evidence_references=(_reference(outra, "evidence"),))

    def test_aceita_balanco_calculado(self) -> None:
        org = _org()
        balanco = TransformationBalance(
            status=BalanceStatus.ASSESSED, result=BalanceResult.BALANCED
        )
        evento = _event(org, balance=balanco)
        assert evento.balance is balanco


class TestTransformationBalance:
    def test_status_deve_ser_balance_status(self) -> None:
        with pytest.raises(TypeError, match="BalanceStatus"):
            TransformationBalance(status="ASSESSED", result=BalanceResult.BALANCED)  # type: ignore[arg-type]

    def test_result_deve_ser_balance_result(self) -> None:
        with pytest.raises(TypeError, match="BalanceResult"):
            TransformationBalance(status=BalanceStatus.ASSESSED, result="BALANCED")  # type: ignore[arg-type]

    def test_totais_nao_aceitam_float(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            TransformationBalance(
                status=BalanceStatus.ASSESSED,
                result=BalanceResult.BALANCED,
                input_total=1.5,  # type: ignore[arg-type]
            )
