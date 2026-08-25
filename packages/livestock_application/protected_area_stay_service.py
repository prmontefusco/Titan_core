"""Permanência do animal em imóvel que declara área protegida no CAR (Passo 17.5).

Este passo **não** decide conformidade nem elegibilidade de mercado, e não é
embargo do IBAMA — esse já tem caminho próprio em
``environmental_embargo_service``. Ele responde a pergunta anterior e mais
estreita que o Passo 17.2 deixou ao alcance: "nos imóveis onde este animal
permaneceu, o CAR declara reserva legal, APP ou uso restrito?".

**O que o Titan sabe e o que não sabe.** A permanência liga o animal ao imóvel,
não a um ponto dentro dele. As camadas do CAR são polígonos internos ao
perímetro. Portanto o resultado positivo diz que o imóvel **declara** área
protegida durante a permanência — nunca que o animal esteve dentro dela. Sem
rastreio de posição intra-imóvel, afirmar o contrário seria inventar
localização. A limitação viaja no resultado, e não no comentário.

Ausência de camada protegida importada também não é prova de ausência de área
protegida: significa que ninguém importou o CAR daquele imóvel. Por isso o
resultado é lacunar, e não negativo.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from packages.livestock_application.geometry_service import PropertyGeometryRepositoryPort
from packages.livestock_domain.geometry import PropertyGeometry
from packages.livestock_domain.movement import PropertyStay
from packages.shared_kernel import OrganizationId, TypedId

# A posição do animal dentro do imóvel é desconhecida por construção. Quem lê o
# resultado precisa ver isso junto do resultado, e não descobrir depois lendo o
# código.
POSICAO_INTRA_IMOVEL_DESCONHECIDA = "LIVESTOCK_POSICAO_DO_ANIMAL_DENTRO_DO_IMOVEL_DESCONHECIDA"


class ProtectedAreaStayStatus(Enum):
    """O que se pode afirmar sobre as permanências do animal."""

    SEM_AREA_PROTEGIDA_DECLARADA = "SEM_AREA_PROTEGIDA_DECLARADA"
    COM_AREA_PROTEGIDA_DECLARADA = "COM_AREA_PROTEGIDA_DECLARADA"
    INDETERMINADA = "INDETERMINADA"


class ProtectedAreaStayGapCode(Enum):
    PERMANENCIA_AUSENTE = "PERMANENCIA_AUSENTE"
    GEOMETRIA_AUSENTE = "GEOMETRIA_AUSENTE"
    CAPTURA_POSTERIOR_A_PERMANENCIA = "CAPTURA_POSTERIOR_A_PERMANENCIA"


@dataclass(frozen=True, slots=True)
class ProtectedAreaStayGap:
    code: ProtectedAreaStayGapCode
    message: str
    property_id: TypedId | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code.value,
            "message": self.message,
            "property_id": None if self.property_id is None else self.property_id.value.hex,
        }


@dataclass(frozen=True, slots=True)
class DeclaredProtectedLayer:
    """Uma camada protegida vigente do imóvel, com a versão que a identifica."""

    layer: str
    geometry_id: TypedId
    geometry_version: int
    captured_at: datetime | None
    layer_version: str | None
    external_reference: str | None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "layer": self.layer,
            "geometry_id": self.geometry_id.value.hex,
            "geometry_version": self.geometry_version,
            "captured_at": None if self.captured_at is None else self.captured_at.isoformat(),
            "layer_version": self.layer_version,
            "external_reference": self.external_reference,
        }


@dataclass(frozen=True, slots=True)
class StayProtectedAreaOverlap:
    """Uma permanência confrontada com as camadas protegidas do imóvel."""

    stay_id: TypedId
    property_id: TypedId
    start_time: datetime
    end_time: datetime | None
    declared_layers: tuple[DeclaredProtectedLayer, ...]

    @property
    def declara_area_protegida(self) -> bool:
        return len(self.declared_layers) > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "stay_id": self.stay_id.value.hex,
            "property_id": self.property_id.value.hex,
            "start_time": self.start_time.isoformat(),
            "end_time": None if self.end_time is None else self.end_time.isoformat(),
            "declared_layers": [layer.to_dict() for layer in self.declared_layers],
        }


@dataclass(frozen=True, slots=True)
class AnimalProtectedAreaStayAssessment:
    animal_id: TypedId
    status: ProtectedAreaStayStatus
    stays: tuple[StayProtectedAreaOverlap, ...]
    limitations: tuple[str, ...]
    gaps: tuple[ProtectedAreaStayGap, ...] = ()

    @property
    def properties_with_declared_area(self) -> tuple[TypedId, ...]:
        return tuple(stay.property_id for stay in self.stays if stay.declara_area_protegida)


class ProtectedAreaStayTimelinePort(Protocol):
    def get_timeline(self, animal_id: TypedId) -> list[PropertyStay]: ...


@dataclass(frozen=True, slots=True)
class ProtectedAreaStayService:
    """Cruza a permanência do animal com as camadas protegidas do CAR do imóvel."""

    stay_repository: ProtectedAreaStayTimelinePort
    geometry_repository: PropertyGeometryRepositoryPort

    def assess_animal(
        self,
        organization_id: OrganizationId,
        animal_id: TypedId,
    ) -> AnimalProtectedAreaStayAssessment:
        if animal_id.entity_type != "animal":
            raise ValueError(
                f"animal_id deve ter entity_type 'animal', recebido '{animal_id.entity_type}'."
            )

        timeline = [
            stay
            for stay in self.stay_repository.get_timeline(animal_id)
            if stay.organization_id == organization_id
        ]
        if not timeline:
            return AnimalProtectedAreaStayAssessment(
                animal_id=animal_id,
                status=ProtectedAreaStayStatus.INDETERMINADA,
                stays=(),
                limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
                gaps=(
                    ProtectedAreaStayGap(
                        code=ProtectedAreaStayGapCode.PERMANENCIA_AUSENTE,
                        message=(
                            "O animal nao tem permanencia registrada; nao ha imovel "
                            "sobre o qual perguntar area protegida."
                        ),
                    ),
                ),
            )

        overlaps: list[StayProtectedAreaOverlap] = []
        gaps: list[ProtectedAreaStayGap] = []

        for stay in timeline:
            layers = [
                geometry
                for geometry in self.geometry_repository.current_layers_for(stay.property_id)
                if geometry.organization_id == organization_id
            ]
            if not layers:
                gaps.append(
                    ProtectedAreaStayGap(
                        code=ProtectedAreaStayGapCode.GEOMETRIA_AUSENTE,
                        message=(
                            "O imovel da permanencia nao tem geometria importada; a "
                            "ausencia de area protegida nao pode ser afirmada."
                        ),
                        property_id=stay.property_id,
                    )
                )

            protegidas = tuple(
                DeclaredProtectedLayer(
                    layer=geometry.layer,
                    geometry_id=geometry.geometry_id,
                    geometry_version=geometry.version,
                    captured_at=geometry.captured_at,
                    layer_version=geometry.layer_version,
                    external_reference=geometry.external_reference,
                )
                for geometry in sorted(layers, key=lambda item: item.layer)
                if geometry.e_area_protegida
            )
            gaps.extend(_capture_gaps(stay, layers))
            overlaps.append(
                StayProtectedAreaOverlap(
                    stay_id=stay.stay_id,
                    property_id=stay.property_id,
                    start_time=stay.start_time,
                    end_time=stay.end_time,
                    declared_layers=protegidas,
                )
            )

        return AnimalProtectedAreaStayAssessment(
            animal_id=animal_id,
            status=_status_for(overlaps, gaps),
            stays=tuple(overlaps),
            limitations=(POSICAO_INTRA_IMOVEL_DESCONHECIDA,),
            gaps=tuple(gaps),
        )


def _capture_gaps(
    stay: PropertyStay,
    layers: list[PropertyGeometry],
) -> list[ProtectedAreaStayGap]:
    """Camada capturada depois da permanência não descreve o período dela.

    O CAR é retificável e ``captured_at`` é a data de atualização do cadastro, não
    a da importação (Passo 17.2). Uma camada cujo cadastro foi atualizado depois de
    o animal sair descreve o imóvel de hoje; usá-la como se descrevesse o período
    da permanência afirmaria sobre um passado que ela não viu.
    """
    if stay.end_time is None:
        return []
    posteriores = sorted(
        geometry.layer
        for geometry in layers
        if geometry.captured_at is not None and geometry.captured_at > stay.end_time
    )
    if not posteriores:
        return []
    return [
        ProtectedAreaStayGap(
            code=ProtectedAreaStayGapCode.CAPTURA_POSTERIOR_A_PERMANENCIA,
            message=(
                "As camadas "
                + ", ".join(posteriores)
                + " foram capturadas depois do fim da permanencia; elas descrevem "
                "o imovel atual, nao o periodo em que o animal esteve nele."
            ),
            property_id=stay.property_id,
        )
    ]


def _status_for(
    overlaps: list[StayProtectedAreaOverlap],
    gaps: list[ProtectedAreaStayGap],
) -> ProtectedAreaStayStatus:
    """Positivo vence lacuna; lacuna vence negativo.

    Uma camada protegida declarada é afirmação da fonte e não deixa de valer
    porque outro imóvel da linha do tempo está sem CAR importado. Já o negativo
    exige que todos os imóveis tenham sido observados: sem isso, "não há área
    protegida" seria conclusão tirada de material que ninguém olhou.
    """
    if any(overlap.declara_area_protegida for overlap in overlaps):
        return ProtectedAreaStayStatus.COM_AREA_PROTEGIDA_DECLARADA
    if gaps:
        return ProtectedAreaStayStatus.INDETERMINADA
    return ProtectedAreaStayStatus.SEM_AREA_PROTEGIDA_DECLARADA
