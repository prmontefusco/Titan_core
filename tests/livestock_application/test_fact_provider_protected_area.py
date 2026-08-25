"""Fato governável de área protegida na permanência (Passo 17.5)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from packages.core_domain.facts import Fact, FactSnapshot
from packages.livestock_application.animal_service import AnimalRepositoryPort
from packages.livestock_application.fact_provider import (
    TERRITORIAL_PROTECTED_AREA_STAY_FACT_TYPE,
    LivestockFactProvider,
)
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_application.protected_area_stay_service import (
    POSICAO_INTRA_IMOVEL_DESCONHECIDA,
    AnimalProtectedAreaStayAssessment,
    DeclaredProtectedLayer,
    ProtectedAreaStayGap,
    ProtectedAreaStayGapCode,
    ProtectedAreaStayStatus,
    StayProtectedAreaOverlap,
)
from packages.livestock_domain.animal import Animal, AnimalSex
from packages.shared_kernel import OrganizationId, TypedId

ORG = OrganizationId.new()
ANIMAL_ID = TypedId.new("animal")
FAZENDA = TypedId.new("rural_property")
AGORA = datetime(2026, 8, 24, tzinfo=UTC)


@dataclass
class EmptyRepository:
    def get_by_id(self, _entity_id: TypedId) -> None:
        return None


@dataclass
class AnimalRepository:
    animal: Animal

    def get_by_id(self, animal_id: TypedId) -> Animal | None:
        return self.animal if self.animal.animal_id == animal_id else None


@dataclass
class ProtectedAreaStayReader:
    assessment: AnimalProtectedAreaStayAssessment

    def assess_animal(
        self, organization_id: OrganizationId, animal_id: TypedId
    ) -> AnimalProtectedAreaStayAssessment:
        return self.assessment


def _animal() -> Animal:
    return Animal(
        animal_id=ANIMAL_ID,
        organization_id=ORG,
        birth_property_id=FAZENDA,
        sex=AnimalSex.FEMALE,
    )


def _permanencia(*camadas: str) -> StayProtectedAreaOverlap:
    return StayProtectedAreaOverlap(
        stay_id=TypedId.new("property_stay"),
        property_id=FAZENDA,
        start_time=datetime(2026, 1, 10, tzinfo=UTC),
        end_time=None,
        declared_layers=tuple(
            DeclaredProtectedLayer(
                layer=camada,
                geometry_id=TypedId.new("property_geometry"),
                geometry_version=1,
                captured_at=None,
                layer_version="v2026-07",
                external_reference="MS-5006606-ABC",
            )
            for camada in camadas
        ),
    )


def _provider(assessment: AnimalProtectedAreaStayAssessment) -> LivestockFactProvider:
    return LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, AnimalRepository(_animal())),
        protected_area_stay_service=ProtectedAreaStayReader(assessment),
    )


def _fato(snapshot: FactSnapshot) -> Fact | None:
    for fato in snapshot.facts:
        if fato.fact_type == TERRITORIAL_PROTECTED_AREA_STAY_FACT_TYPE:
            return fato
    return None


def test_area_protegida_declarada_vira_fato_com_chave_afirmativa() -> None:
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA,
            stays=(_permanencia("RESERVA_LEGAL"),),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
        )
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)
    fato = _fato(snapshot)

    assert fato is not None
    payload = fato.payload
    assert payload["status"] == "COM_AREA_PROTEGIDA_DECLARADA"
    assert payload["has_declared_protected_area"] is True
    assert payload["declared_layers"] == ["RESERVA_LEGAL"]
    assert payload["properties_with_declared_area"] == [FAZENDA.value.hex]
    assert payload["gaps"] == []


def test_ausencia_declarada_nao_afirma_area_protegida() -> None:
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.SEM_AREA_PROTEGIDA_DECLARADA,
            stays=(_permanencia(),),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
        )
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)
    fato = _fato(snapshot)

    assert fato is not None
    assert fato.payload["has_declared_protected_area"] is False
    assert fato.payload["declared_layers"] == []
    assert fato.payload["gaps"] == []


def test_indeterminada_leva_a_lacuna_junto_da_chave_negativa() -> None:
    """Uma regra que ler só `has_declared_protected_area` leria lacuna como ausência."""
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.INDETERMINADA,
            stays=(_permanencia(),),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
            gaps=(
                ProtectedAreaStayGap(
                    code=ProtectedAreaStayGapCode.GEOMETRIA_AUSENTE,
                    message="sem CAR importado",
                    property_id=FAZENDA,
                ),
            ),
        )
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)
    fato = _fato(snapshot)

    assert fato is not None
    assert fato.payload["status"] == "INDETERMINADA"
    assert fato.payload["has_declared_protected_area"] is False
    assert fato.payload["gaps"] == [
        {
            "code": "GEOMETRIA_AUSENTE",
            "message": "sem CAR importado",
            "property_id": FAZENDA.value.hex,
        }
    ]


def test_camadas_de_permanencias_distintas_entram_deduplicadas_e_ordenadas() -> None:
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA,
            stays=(
                _permanencia("USO_RESTRITO", "RESERVA_LEGAL"),
                _permanencia("RESERVA_LEGAL", "APPS"),
            ),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
        )
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)
    fato = _fato(snapshot)

    assert fato is not None
    assert fato.payload["declared_layers"] == ["APPS", "RESERVA_LEGAL", "USO_RESTRITO"]
    assert fato.payload["stay_count"] == 2


def test_limitacao_de_posicao_viaja_no_fato() -> None:
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA,
            stays=(_permanencia("APPS"),),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
        )
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)
    fato = _fato(snapshot)

    assert fato is not None
    assert POSICAO_INTRA_IMOVEL_DESCONHECIDA in fato.payload["limitations"]


def test_sem_o_servico_configurado_o_fato_nao_existe() -> None:
    """Ausência do serviço não pode virar fato negativo silencioso."""
    provider = LivestockFactProvider(
        property_repository=cast(RuralPropertyRepositoryPort, EmptyRepository()),
        animal_repository=cast(AnimalRepositoryPort, AnimalRepository(_animal())),
    )

    snapshot = provider.get_snapshot(ORG, ANIMAL_ID, AGORA)

    assert _fato(snapshot) is None


def test_fato_nao_entra_na_leitura_temporal() -> None:
    """`PropertyStay` é projeção mutável e não sustenta reprodução histórica."""
    provider = _provider(
        AnimalProtectedAreaStayAssessment(
            animal_id=ANIMAL_ID,
            status=ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA,
            stays=(_permanencia("RESERVA_LEGAL"),),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
        )
    )

    snapshot = provider.get_snapshot_with_temporal_context(
        ORG,
        ANIMAL_ID,
        reference_time=AGORA,
        knowledge_cutoff=AGORA,
    )

    assert _fato(snapshot) is None
    assert (
        "LIVESTOCK_CURRENT_STATE_NOT_HISTORICALLY_RECONSTRUCTABLE" in snapshot.knowledge_limitations
    )
