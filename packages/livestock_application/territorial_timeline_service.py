"""Leitura temporal territorial sobre a propriedade vigente.

Este passo ainda nao decide conformidade nem elegibilidade de mercado. Ele
responde a uma pergunta anterior e mais estreita: "que serie temporal o provider
territorial declara para esta propriedade, nesta camada e neste intervalo?".

O Titan nao inventa o `cod_imovel`: reaproveita a `external_reference` da
geometria vigente importada do CAR. Sem essa referencia, a pergunta temporal por
codigo externo fica lacunar e o servico a declara assim.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from packages.livestock_application.geometry_service import PropertyGeometryRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.geometry import CAMADA_PERIMETRO, PropertyGeometry
from packages.livestock_domain.property import RuralProperty
from packages.livestock_infrastructure.geodata import TerritorialTimelineAssessment
from packages.shared_kernel import OrganizationId, TypedId


class TerritorialTimelineStatus(Enum):
    DISPONIVEL = "DISPONIVEL"
    INDETERMINADA = "INDETERMINADA"


class TerritorialTimelineGapCode(Enum):
    GEOMETRIA_AUSENTE = "GEOMETRIA_AUSENTE"
    REFERENCIA_EXTERNA_AUSENTE = "REFERENCIA_EXTERNA_AUSENTE"


@dataclass(frozen=True, slots=True)
class TerritorialTimelineGap:
    code: TerritorialTimelineGapCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class PropertyTerritorialTimelineAssessment:
    property_id: TypedId
    geometry_id: TypedId | None
    geometry_version: int | None
    external_reference: str | None
    source: str
    layer: str
    status: TerritorialTimelineStatus
    property_area_hectares: float | None
    year_from: int | None
    year_to: int | None
    years: tuple[dict[str, object], ...]
    response_digest: str | None
    gaps: tuple[TerritorialTimelineGap, ...] = ()


class TerritorialTimelineLookupPort(Protocol):
    def fetch_prodes_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment: ...

    def fetch_deter_timeline(
        self,
        *,
        cod_imovel: str,
        state: str,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> TerritorialTimelineAssessment: ...


@dataclass(frozen=True, slots=True)
class TerritorialTimelineService:
    property_repository: RuralPropertyRepositoryPort
    geometry_repository: PropertyGeometryRepositoryPort
    geodata_lookup: TerritorialTimelineLookupPort

    def assess_prodes_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment:
        property_found = self.property_repository.get_by_id(property_id)
        if property_found is None or property_found.organization_id != organization_id:
            raise KeyError(f"Propriedade '{property_id.value}' nao encontrada.")

        geometry = self.geometry_repository.current_for(property_id, CAMADA_PERIMETRO)
        if geometry is None or geometry.organization_id != organization_id:
            return PropertyTerritorialTimelineAssessment(
                property_id=property_id,
                geometry_id=None,
                geometry_version=None,
                external_reference=None,
                source="INPE/TerraBrasilis",
                layer="TB_PRODES",
                status=TerritorialTimelineStatus.INDETERMINADA,
                property_area_hectares=None,
                year_from=year_from,
                year_to=year_to,
                years=(),
                response_digest=None,
                gaps=(
                    TerritorialTimelineGap(
                        code=TerritorialTimelineGapCode.GEOMETRIA_AUSENTE,
                        message=(
                            "A propriedade ainda nao tem geometria vigente; a consulta "
                            "temporal territorial nao pode ser executada."
                        ),
                    ),
                ),
            )

        if geometry.external_reference is None:
            return PropertyTerritorialTimelineAssessment(
                property_id=property_id,
                geometry_id=geometry.geometry_id,
                geometry_version=geometry.version,
                external_reference=None,
                source="INPE/TerraBrasilis",
                layer="TB_PRODES",
                status=TerritorialTimelineStatus.INDETERMINADA,
                property_area_hectares=None,
                year_from=year_from,
                year_to=year_to,
                years=(),
                response_digest=None,
                gaps=(
                    TerritorialTimelineGap(
                        code=TerritorialTimelineGapCode.REFERENCIA_EXTERNA_AUSENTE,
                        message=(
                            "A geometria vigente nao declara a referencia externa do CAR; "
                            "a consulta temporal por cod_imovel nao pode ser reproduzida."
                        ),
                    ),
                ),
            )

        state = _state_for_lookup(
            external_reference=geometry.external_reference,
            fallback_state=property_found.state_code,
        )
        timeline = self.geodata_lookup.fetch_prodes_timeline(
            cod_imovel=geometry.external_reference,
            state=state,
            year_from=year_from,
            year_to=year_to,
        )
        return _map_timeline_result(
            property_found=property_found,
            geometry=geometry,
            timeline=timeline,
            year_from=year_from,
            year_to=year_to,
            default_source="INPE/TerraBrasilis",
            default_layer="TB_PRODES",
        )

    def assess_deter_timeline(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
        *,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> PropertyTerritorialTimelineAssessment:
        property_found = self.property_repository.get_by_id(property_id)
        if property_found is None or property_found.organization_id != organization_id:
            raise KeyError(f"Propriedade '{property_id.value}' nao encontrada.")

        geometry = self.geometry_repository.current_for(property_id, CAMADA_PERIMETRO)
        if geometry is None or geometry.organization_id != organization_id:
            return _gap_result(
                property_id=property_id,
                geometry_id=None,
                geometry_version=None,
                external_reference=None,
                source="INPE/TerraBrasilis",
                layer="TB_DETER",
                year_from=year_from,
                year_to=year_to,
                code=TerritorialTimelineGapCode.GEOMETRIA_AUSENTE,
                message=(
                    "A propriedade ainda nao tem geometria vigente; a consulta "
                    "temporal territorial nao pode ser executada."
                ),
            )

        if geometry.external_reference is None:
            return _gap_result(
                property_id=property_id,
                geometry_id=geometry.geometry_id,
                geometry_version=geometry.version,
                external_reference=None,
                source="INPE/TerraBrasilis",
                layer="TB_DETER",
                year_from=year_from,
                year_to=year_to,
                code=TerritorialTimelineGapCode.REFERENCIA_EXTERNA_AUSENTE,
                message=(
                    "A geometria vigente nao declara a referencia externa do CAR; "
                    "a consulta temporal por cod_imovel nao pode ser reproduzida."
                ),
            )

        state = _state_for_lookup(
            external_reference=geometry.external_reference,
            fallback_state=property_found.state_code,
        )
        timeline = self.geodata_lookup.fetch_deter_timeline(
            cod_imovel=geometry.external_reference,
            state=state,
            year_from=year_from,
            year_to=year_to,
        )
        return _map_timeline_result(
            property_found=property_found,
            geometry=geometry,
            timeline=timeline,
            year_from=year_from,
            year_to=year_to,
            default_source="INPE/TerraBrasilis",
            default_layer="TB_DETER",
        )


def _gap_result(
    *,
    property_id: TypedId,
    geometry_id: TypedId | None,
    geometry_version: int | None,
    external_reference: str | None,
    source: str,
    layer: str,
    year_from: int | None,
    year_to: int | None,
    code: TerritorialTimelineGapCode,
    message: str,
) -> PropertyTerritorialTimelineAssessment:
    return PropertyTerritorialTimelineAssessment(
        property_id=property_id,
        geometry_id=geometry_id,
        geometry_version=geometry_version,
        external_reference=external_reference,
        source=source,
        layer=layer,
        status=TerritorialTimelineStatus.INDETERMINADA,
        property_area_hectares=None,
        year_from=year_from,
        year_to=year_to,
        years=(),
        response_digest=None,
        gaps=(TerritorialTimelineGap(code=code, message=message),),
    )


def _map_timeline_result(
    *,
    property_found: RuralProperty,
    geometry: PropertyGeometry,
    timeline: TerritorialTimelineAssessment,
    year_from: int | None,
    year_to: int | None,
    default_source: str,
    default_layer: str,
) -> PropertyTerritorialTimelineAssessment:
    return PropertyTerritorialTimelineAssessment(
        property_id=property_found.property_id,
        geometry_id=geometry.geometry_id,
        geometry_version=geometry.version,
        external_reference=geometry.external_reference,
        source=timeline.source or default_source,
        layer=timeline.layer or default_layer,
        status=TerritorialTimelineStatus.DISPONIVEL,
        property_area_hectares=timeline.property_area_hectares,
        year_from=timeline.year_from if timeline.year_from is not None else year_from,
        year_to=timeline.year_to if timeline.year_to is not None else year_to,
        years=tuple(
            {
                "year": item.year,
                "feature_count": item.feature_count,
                "overlap_area_hectares": item.overlap_area_hectares,
                "source_area_hectares": item.source_area_hectares,
                "version_ids": list(item.version_ids),
            }
            for item in timeline.years
        ),
        response_digest=timeline.response_digest,
    )


def _state_for_lookup(*, external_reference: str, fallback_state: str) -> str:
    prefix, _, _ = external_reference.partition("-")
    normalized = prefix.strip().upper()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return fallback_state
