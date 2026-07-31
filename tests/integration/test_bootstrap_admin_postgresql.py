import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from apps.bootstrap_admin.__main__ import BootstrapAdminSettings, apply_admin_bootstrap
from packages.core_domain import Organization
from packages.core_infrastructure.persistence import (
    OrganizationRepository,
    set_local_organization_context,
)
from packages.livestock_application.authorization import ADMIN_MESTRE, ADMINISTRACAO
from packages.shared_kernel import OrganizationId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


def _settings(operadora: OrganizationId, alvo: OrganizationId) -> BootstrapAdminSettings:
    return BootstrapAdminSettings(
        operator_organization_id=operadora,
        target_organization_id=alvo,
        issuer="http://localhost:8080/realms/titan",
        subject=f"admin-teste-{uuid4().hex}",
        authority_actor_id=uuid4(),
    )


def test_bootstrap_concede_admin_mestre_com_permissoes_da_administracao() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection, connection.begin() as transacao:
            operadora = Organization.create()
            set_local_organization_context(connection, operadora.organization_id)
            OrganizationRepository(connection).add(operadora)
            alvo = OrganizationId.new()
            transacao.commit()  # apply_admin_bootstrap abre a própria transação

        settings = _settings(operadora.organization_id, alvo)
        resultado = apply_admin_bootstrap(engine, settings)

        assert resultado["organization_id"] == str(alvo.value)

        with engine.connect() as connection, connection.begin():
            set_local_organization_context(connection, alvo)
            papel = connection.execute(
                text("SELECT name FROM core_identity.roles WHERE role_id = :r"),
                {"r": resultado["role_id"]},
            ).scalar_one()
            assert papel == ADMIN_MESTRE

            codigos = connection.execute(
                text(
                    "SELECT p.code FROM core_identity.role_permissions rp "
                    "JOIN core_identity.permissions p ON p.permission_id = rp.permission_id "
                    "WHERE rp.role_id = :r"
                ),
                {"r": resultado["role_id"]},
            ).scalars()
            assert set(codigos) == ADMINISTRACAO

            membership_status = connection.execute(
                text("SELECT status FROM core_identity.memberships WHERE membership_id = :m"),
                {"m": resultado["membership_id"]},
            ).scalar_one()
            assert membership_status == "ATIVA"
            connection.rollback()
    finally:
        engine.dispose()


def test_bootstrap_e_idempotente_para_organization_e_identidade() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection, connection.begin() as transacao:
            operadora = Organization.create()
            set_local_organization_context(connection, operadora.organization_id)
            OrganizationRepository(connection).add(operadora)
            alvo = OrganizationId.new()
            transacao.commit()

        settings = _settings(operadora.organization_id, alvo)
        primeira = apply_admin_bootstrap(engine, settings)
        segunda = apply_admin_bootstrap(engine, settings)

        # Organization, User e Role são reaproveitados -- só o Membership novo.
        assert primeira["organization_id"] == segunda["organization_id"]
        assert primeira["user_id"] == segunda["user_id"]
        assert primeira["role_id"] == segunda["role_id"]
        assert primeira["membership_id"] != segunda["membership_id"]

        with engine.connect() as connection, connection.begin():
            set_local_organization_context(connection, alvo)
            total_papeis = connection.execute(
                text(
                    "SELECT count(*) FROM core_identity.roles "
                    "WHERE organization_id = :o AND name = :n"
                ),
                {"o": alvo.value, "n": ADMIN_MESTRE},
            ).scalar_one()
            assert total_papeis == 1
            connection.rollback()
    finally:
        engine.dispose()
