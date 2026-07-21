from pathlib import Path
from uuid import uuid4

import pytest

from packages.core_infrastructure.bootstrap import (
    ALLOWED_ENVIRONMENTS,
    BOOTSTRAP_PROFILE_CODE,
    BootstrapConfigurationError,
    BootstrapSettings,
    bootstrap_receipts_table,
)


def test_bootstrap_settings_require_explicit_identifiers_and_controlled_environment() -> None:
    organization_id = uuid4()
    authority_id = uuid4()

    settings = BootstrapSettings.from_environment(
        {
            "TITAN_OPERATOR_ORGANIZATION_ID": str(organization_id),
            "TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID": str(authority_id),
            "TITAN_ENVIRONMENT": "DESENVOLVIMENTO",
        }
    )

    assert settings.operator_organization_id.value == organization_id
    assert settings.authority_actor_id == authority_id
    assert settings.environment in ALLOWED_ENVIRONMENTS


@pytest.mark.parametrize(
    "environment",
    [{}, {"TITAN_ENVIRONMENT": "development"}],
)
def test_bootstrap_settings_fail_closed(environment: dict[str, str]) -> None:
    with pytest.raises(BootstrapConfigurationError):
        BootstrapSettings.from_environment(environment)


def test_bootstrap_receipt_contract_is_minimal_and_protected() -> None:
    assert "PROTECTED" in str(bootstrap_receipts_table.comment)
    assert BOOTSTRAP_PROFILE_CODE == "ORGANIZATION_OPERADORA_MINIMA"
    assert "permission_id" not in bootstrap_receipts_table.c
    assert "role_id" not in bootstrap_receipts_table.c
    assert "user_id" not in bootstrap_receipts_table.c


def test_bootstrap_migration_is_reversible_and_forces_rls() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260721_0007_create_bootstrap_receipts.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0007"' in source
    assert 'down_revision: str | None = "20260721_0006"' in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "REVOKE ALL ON core_identity.bootstrap_receipts FROM PUBLIC" in source
    assert "op.drop_table(TABLE, schema=SCHEMA)" in source
