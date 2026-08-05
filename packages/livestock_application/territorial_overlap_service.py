"""Leitura territorial atual sobre a propriedade vigente.

FUNAI entra como restricao territorial presente, e nao como serie temporal.
Este servico responde: ha sobreposicao atual conhecida desta camada para a
propriedade?
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from packages.livestock_application.geometry_service import PropertyGeometryRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_domain.geometry import CAMADA_PERIMETRO
from packages.livestock_infrastructure.geodata import TerritorialOverlapAssessment
from packages.shared_kernel import OrganizationId, TypedId


class TerritorialOverlapStatus(Enum):
    SEM_RESTRICAO = "SEM_RESTRICAO"
    COM_RESTRICAO = "COM_RESTRICAO"
    INDETERMINADA = "INDETERMINADA"


class TerritorialOverlapGapCode(Enum):
    GEOMETRIA_AUSENTE = "GEOMETRIA_AUSENTE"
    REFERENCIA_EXTERNA_AUSENTE = "REFERENCIA_EXTERNA_AUSENTE"


@dataclass(frozen=True, slots=True)
class TerritorialOverlapGap:
    code: TerritorialOverlapGapCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class PropertyTerritorialOverlapAssessment:
    property_id: TypedId
    geometry_id: TypedId | None
    geometry_version: int | None
    external_reference: str | None
    source: str
    layer: str
    label: str
    status: TerritorialOverlapStatus
    feature_count: int
    area_hectares: float | None
    source_area_hectares: float | None
    version_ids: tuple[str, ...]
    response_digest: str | None
    gaps: tuple[TerritorialOverlapGap, ...] = ()


class TerritorialOverlapLookupPort(Protocol):
    def fetch_funai_overlap(
        self,
        *,
        cod_imovel: str,
        state: str,
    ) -> TerritorialOverlapAssessment: ...


@dataclass(frozen=True, slots=True)
class TerritorialOverlapService:
    property_repository: RuralPropertyRepositoryPort
    geometry_repository: PropertyGeometryRepositoryPort
    geodata_lookup: TerritorialOverlapLookupPort

    def assess_funai_overlap(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
    ) -> PropertyTerritorialOverlapAssessment:
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
                code=TerritorialOverlapGapCode.GEOMETRIA_AUSENTE,
                message=(
                    "A propriedade ainda nao tem geometria vigente; a consulta "
                    "territorial atual nao pode ser executada."
                ),
            )

        if geometry.external_reference is None:
            return _gap_result(
                property_id=property_id,
                geometry_id=geometry.geometry_id,
                geometry_version=geometry.version,
                external_reference=None,
                code=TerritorialOverlapGapCode.REFERENCIA_EXTERNA_AUSENTE,
                message=(
                    "A geometria vigente nao declara a referencia externa do CAR; "
                    "a consulta territorial por cod_imovel nao pode ser reproduzida."
                ),
            )

        state = _state_for_lookup(
            external_reference=geometry.external_reference,
            fallback_state=property_found.state_code,
        )
        overlap = self.geodata_lookup.fetch_funai_overlap(
            cod_imovel=geometry.external_reference,
            state=state,
        )
        return PropertyTerritorialOverlapAssessment(
            property_id=property_id,
            geometry_id=geometry.geometry_id,
            geometry_version=geometry.version,
            external_reference=geometry.external_reference,
            source=overlap.source,
            layer=overlap.layer,
            label=overlap.label,
            status=(
                TerritorialOverlapStatus.COM_RESTRICAO
                if overlap.feature_count > 0
                else TerritorialOverlapStatus.SEM_RESTRICAO
            ),
            feature_count=overlap.feature_count,
            area_hectares=overlap.area_hectares,
            source_area_hectares=overlap.source_area_hectares,
            version_ids=overlap.version_ids,
            response_digest=overlap.response_digest,
        )


def _gap_result(
    *,
    property_id: TypedId,
    geometry_id: TypedId | None,
    geometry_version: int | None,
    external_reference: str | None,
    code: TerritorialOverlapGapCode,
    message: str,
) -> PropertyTerritorialOverlapAssessment:
    return PropertyTerritorialOverlapAssessment(
        property_id=property_id,
        geometry_id=geometry_id,
        geometry_version=geometry_version,
        external_reference=external_reference,
        source="FUNAI",
        layer="FUNAI_TI",
        label="Terras Indigenas (FUNAI)",
        status=TerritorialOverlapStatus.INDETERMINADA,
        feature_count=0,
        area_hectares=None,
        source_area_hectares=None,
        version_ids=(),
        response_digest=None,
        gaps=(TerritorialOverlapGap(code=code, message=message),),
    )


def _state_for_lookup(*, external_reference: str, fallback_state: str) -> str:
    prefix, _, _ = external_reference.partition("-")
    normalized = prefix.strip().upper()
    if len(normalized) == 2 and normalized.isalpha():
        return normalized
    return fallback_state
