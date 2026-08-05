"""Integração com providers geoespaciais externos (Passo 17.2, ADR-0026)."""

from packages.livestock_infrastructure.geodata.car_client import (
    CarLayer,
    CarLookupPort,
    CarNaoEncontrado,
    CarProperty,
    GeodataCarClient,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
    SpatialRestriction,
    SpatialRestrictionAssessment,
    TerritorialOverlapAssessment,
    TerritorialTimelineAssessment,
    TerritorialTimelineYear,
    interpretar_camada,
    interpretar_resposta,
    interpretar_restricoes_espaciais,
    interpretar_timeline_territorial,
)

__all__ = [
    "CarLayer",
    "CarLookupPort",
    "CarNaoEncontrado",
    "CarProperty",
    "GeodataCarClient",
    "GeodataIndisponivel",
    "GeodataNaoConfigurado",
    "SpatialRestriction",
    "SpatialRestrictionAssessment",
    "TerritorialOverlapAssessment",
    "TerritorialTimelineAssessment",
    "TerritorialTimelineYear",
    "interpretar_camada",
    "interpretar_restricoes_espaciais",
    "interpretar_resposta",
    "interpretar_timeline_territorial",
]
