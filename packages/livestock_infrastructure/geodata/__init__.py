"""Integração com providers geoespaciais externos (Passo 17.2, ADR-0026)."""

from packages.livestock_infrastructure.geodata.car_client import (
    CarLayer,
    CarLookupPort,
    CarNaoEncontrado,
    CarProperty,
    GeodataCarClient,
    GeodataIndisponivel,
    GeodataNaoConfigurado,
    interpretar_camada,
    interpretar_resposta,
)

__all__ = [
    "CarLayer",
    "CarLookupPort",
    "CarNaoEncontrado",
    "CarProperty",
    "GeodataCarClient",
    "GeodataIndisponivel",
    "GeodataNaoConfigurado",
    "interpretar_camada",
    "interpretar_resposta",
]
