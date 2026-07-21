"""Entrada do bootstrap administrativo mínimo."""

import json

from packages.core_infrastructure.bootstrap import BootstrapSettings, apply_minimum_bootstrap
from packages.core_infrastructure.persistence import DatabaseSettings, create_database_engine


def main() -> None:
    database_settings = DatabaseSettings.from_environment()
    bootstrap_settings = BootstrapSettings.from_environment()
    engine = create_database_engine(database_settings)
    try:
        outcome = apply_minimum_bootstrap(engine, bootstrap_settings)
    finally:
        engine.dispose()
    print(
        json.dumps(
            {
                "resultado": outcome.result.value,
                "organization_id": str(outcome.organization_id),
                "perfil": outcome.profile_code,
                "versao": outcome.profile_version,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
