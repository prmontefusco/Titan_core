"""Avaliacao espacial de embargos ambientais sobre a geometria da propriedade.

Este passo NAO decide conformidade nem elegibilidade de mercado. Ele responde
uma pergunta anterior e mais estreita: "quais restricoes o provider declarou
que intersectam o poligono vigente desta propriedade?".

Sem essa separacao, o adapter HTTP passaria a decidir negocio e o dominio
passaria a depender do provider. O Titan consome a observacao, identifica a
versao da geometria e da base consultada, e deixa a conclusao regulatoria para
regras versionadas posteriores.
"""

from dataclasses import dataclass
from enum import Enum

from packages.livestock_application.geometry_service import PropertyGeometryRepositoryPort
from packages.livestock_application.property_service import RuralPropertyRepositoryPort
from packages.livestock_infrastructure.geodata import CarLookupPort, SpatialRestriction
from packages.shared_kernel import OrganizationId, TypedId


class EnvironmentalEmbargoStatus(Enum):
    SEM_RESTRICAO = "SEM_RESTRICAO"
    COM_RESTRICAO = "COM_RESTRICAO"
    INDETERMINADA = "INDETERMINADA"


class EnvironmentalEmbargoGapCode(Enum):
    GEOMETRIA_AUSENTE = "GEOMETRIA_AUSENTE"


@dataclass(frozen=True, slots=True)
class EnvironmentalEmbargoGap:
    code: EnvironmentalEmbargoGapCode
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code.value, "message": self.message}


@dataclass(frozen=True, slots=True)
class EnvironmentalEmbargoAssessment:
    property_id: TypedId
    geometry_id: TypedId | None
    source: str
    layer: str
    operation: str
    status: EnvironmentalEmbargoStatus
    geometry_version: int | None
    source_digest: str | None
    version_ids: tuple[str, ...]
    restrictions: tuple[SpatialRestriction, ...]
    response_digest: str | None
    gaps: tuple[EnvironmentalEmbargoGap, ...] = ()

    @property
    def restriction_count(self) -> int:
        return len(self.restrictions)


@dataclass(frozen=True, slots=True)
class EnvironmentalEmbargoService:
    property_repository: RuralPropertyRepositoryPort
    geometry_repository: PropertyGeometryRepositoryPort
    geodata_lookup: CarLookupPort

    def assess_ibama_embargoes(
        self,
        organization_id: OrganizationId,
        property_id: TypedId,
    ) -> EnvironmentalEmbargoAssessment:
        property_found = self.property_repository.get_by_id(property_id)
        if property_found is None or property_found.organization_id != organization_id:
            raise KeyError(f"Propriedade '{property_id.value}' nao encontrada.")

        geometry = self.geometry_repository.current_for(property_id)
        if geometry is None or geometry.organization_id != organization_id:
            return EnvironmentalEmbargoAssessment(
                property_id=property_id,
                geometry_id=None,
                source="IBAMA",
                layer="IBAMA_EMBARGOS",
                operation="intersects",
                status=EnvironmentalEmbargoStatus.INDETERMINADA,
                geometry_version=None,
                source_digest=None,
                version_ids=(),
                restrictions=(),
                response_digest=None,
                gaps=(
                    EnvironmentalEmbargoGap(
                        code=EnvironmentalEmbargoGapCode.GEOMETRIA_AUSENTE,
                        message=(
                            "A propriedade ainda nao tem geometria vigente; a avaliacao "
                            "espacial nao pode ser executada."
                        ),
                    ),
                ),
            )

        spatial = self.geodata_lookup.fetch_ibama_overlaps(
            polygon_payload=geometry.source_payload,
            srid=geometry.srid,
        )
        return EnvironmentalEmbargoAssessment(
            property_id=property_id,
            geometry_id=geometry.geometry_id,
            source=spatial.source,
            layer=spatial.layer,
            operation=spatial.operation,
            status=(
                EnvironmentalEmbargoStatus.COM_RESTRICAO
                if spatial.restriction_count > 0
                else EnvironmentalEmbargoStatus.SEM_RESTRICAO
            ),
            geometry_version=geometry.version,
            source_digest=geometry.source_digest,
            version_ids=spatial.version_ids,
            restrictions=spatial.restrictions,
            response_digest=spatial.response_digest,
        )
