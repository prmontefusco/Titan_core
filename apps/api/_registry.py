"""Registro aditivo de routers HTTP da API Titan.

P3 da trilha Asset exige que `main.py` deixe de conhecer manualmente cada
router de vertical antes de A5. Este módulo só centraliza a composição: não
move routers existentes, não altera paths e não cria endpoints novos.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from os import environ

from fastapi import APIRouter

from apps.api.asset.commands import router as asset_commands_router
from apps.api.asset.queries import router as asset_queries_router
from apps.api.livestock_animals import router as livestock_animals_router
from apps.api.livestock_commercial_passport import router as livestock_commercial_passport_router
from apps.api.livestock_entity_type_requests import router as livestock_entity_type_requests_router
from apps.api.livestock_market_optionality_explanation import (
    router as livestock_market_optionality_explanation_router,
)
from apps.api.livestock_market_supply import router as livestock_market_supply_router
from apps.api.livestock_medications import router as livestock_medications_router
from apps.api.livestock_queries import router as livestock_queries_router
from apps.api.livestock_reads import router as livestock_reads_router
from apps.api.livestock_sanitary_campaigns import router as livestock_sanitary_campaigns_router
from apps.api.livestock_transformations import router as livestock_transformations_router
from apps.api.livestock_treatments import router as livestock_treatments_router
from apps.api.livestock_writes import router as livestock_writes_router


@dataclass(frozen=True, slots=True)
class ApiRouterRegistration:
    """Router registrado pela composição da API.

    `enabled` permite preservar os release gates atuais: rotas opcionais só
    entram no OpenAPI quando a respectiva feature flag está ativa.
    """

    router: APIRouter
    enabled: Callable[[], bool] = lambda: True


def _flag_enabled(name: str) -> Callable[[], bool]:
    return lambda: environ.get(name, "").casefold() == "true"


ALWAYS_ON_ROUTERS: tuple[ApiRouterRegistration, ...] = (
    ApiRouterRegistration(asset_commands_router),
    ApiRouterRegistration(asset_queries_router),
    ApiRouterRegistration(livestock_animals_router),
    ApiRouterRegistration(livestock_medications_router),
    ApiRouterRegistration(livestock_sanitary_campaigns_router),
    ApiRouterRegistration(livestock_treatments_router),
    ApiRouterRegistration(livestock_queries_router),
    ApiRouterRegistration(livestock_reads_router),
    ApiRouterRegistration(livestock_writes_router),
    ApiRouterRegistration(livestock_transformations_router),
    ApiRouterRegistration(livestock_entity_type_requests_router),
)


FEATURE_FLAGGED_ROUTERS: tuple[ApiRouterRegistration, ...] = (
    ApiRouterRegistration(
        livestock_market_supply_router,
        enabled=_flag_enabled("TITAN_MARKET_SUPPLY_AGGREGATE_API_ENABLED"),
    ),
    ApiRouterRegistration(
        livestock_market_optionality_explanation_router,
        enabled=_flag_enabled("TITAN_MARKET_OPTIONALITY_AI_EXPLANATION_API_ENABLED"),
    ),
    ApiRouterRegistration(
        livestock_commercial_passport_router,
        enabled=_flag_enabled("TITAN_COMMERCIAL_PASSPORT_API_ENABLED"),
    ),
)


def enabled_api_routers() -> Iterable[APIRouter]:
    for registration in ALWAYS_ON_ROUTERS + FEATURE_FLAGGED_ROUTERS:
        if registration.enabled():
            yield registration.router
