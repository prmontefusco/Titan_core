"""Bootstrap administrativo mínimo e auditável do Titan."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import insert

from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
    organization_metadata,
    organizations_table,
    set_local_organization_context,
)
from packages.shared_kernel import OrganizationId

BOOTSTRAP_PROFILE_CODE = "ORGANIZATION_OPERADORA_MINIMA"
BOOTSTRAP_PROFILE_VERSION = "1"
BOOTSTRAP_ORIGIN = "apps.bootstrap"
ALLOWED_ENVIRONMENTS = frozenset({"DESENVOLVIMENTO", "TESTE", "HOMOLOGACAO", "PRODUCAO"})

bootstrap_receipts_table = Table(
    "bootstrap_receipts",
    organization_metadata,
    Column("bootstrap_receipt_id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    Column(
        "record_owner_organization_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "core_identity.organizations.organization_id",
            name="fk_bootstrap_receipts_owner",
        ),
        nullable=False,
    ),
    Column("profile_code", String(100), nullable=False),
    Column("profile_version", String(30), nullable=False),
    Column("environment", String(30), nullable=False),
    Column("origin", String(100), nullable=False),
    Column("authority_actor_id", PostgreSQLUUID(as_uuid=True), nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
    Column("result", String(30), nullable=False),
    CheckConstraint("result = 'APLICADO'", name="ck_bootstrap_receipts_result"),
    UniqueConstraint(
        "profile_code",
        "profile_version",
        "environment",
        name="uq_bootstrap_receipts_profile_environment",
    ),
    schema=CORE_IDENTITY_SCHEMA,
    comment="titan.classification=PROTECTED;titan.module_owner=core_identity",
)


class BootstrapConfigurationError(ValueError):
    """Indica configuração administrativa ausente ou inválida."""


class BootstrapResult(StrEnum):
    APLICADO = "APLICADO"
    JA_APLICADO = "JA_APLICADO"


@dataclass(frozen=True, slots=True)
class BootstrapSettings:
    operator_organization_id: OrganizationId
    authority_actor_id: UUID
    environment: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "BootstrapSettings":
        source = os.environ if environment is None else environment
        organization_id = _required_uuid(source, "TITAN_OPERATOR_ORGANIZATION_ID")
        authority_actor_id = _required_uuid(source, "TITAN_BOOTSTRAP_AUTHORITY_ACTOR_ID")
        environment_name = source.get("TITAN_ENVIRONMENT", "")
        if environment_name not in ALLOWED_ENVIRONMENTS:
            allowed = ", ".join(sorted(ALLOWED_ENVIRONMENTS))
            raise BootstrapConfigurationError(
                f"TITAN_ENVIRONMENT deve ser um destes valores: {allowed}."
            )
        return cls(
            operator_organization_id=OrganizationId(organization_id),
            authority_actor_id=authority_actor_id,
            environment=environment_name,
        )


@dataclass(frozen=True, slots=True)
class BootstrapOutcome:
    result: BootstrapResult
    organization_id: OrganizationId
    profile_code: str = BOOTSTRAP_PROFILE_CODE
    profile_version: str = BOOTSTRAP_PROFILE_VERSION


def apply_minimum_bootstrap(engine: Engine, settings: BootstrapSettings) -> BootstrapOutcome:
    """Aplica ou confirma atomicamente o perfil mínimo aprovado."""
    if not isinstance(engine, Engine):
        raise TypeError("engine deve ser um Engine SQLAlchemy.")
    if not isinstance(settings, BootstrapSettings):
        raise TypeError("settings deve ser BootstrapSettings.")

    organization_value = settings.operator_organization_id.value
    with engine.begin() as connection:
        set_local_organization_context(connection, settings.operator_organization_id)
        existing = connection.execute(
            select(
                bootstrap_receipts_table.c.record_owner_organization_id,
                bootstrap_receipts_table.c.authority_actor_id,
            ).where(
                bootstrap_receipts_table.c.profile_code == BOOTSTRAP_PROFILE_CODE,
                bootstrap_receipts_table.c.profile_version == BOOTSTRAP_PROFILE_VERSION,
                bootstrap_receipts_table.c.environment == settings.environment,
            )
        ).one_or_none()
        if existing is not None:
            if existing.record_owner_organization_id != organization_value:
                raise BootstrapConfigurationError(
                    "O ambiente já possui outra Organization operadora registrada."
                )
            return BootstrapOutcome(BootstrapResult.JA_APLICADO, settings.operator_organization_id)

        connection.execute(
            insert(organizations_table)
            .values(
                organization_id=organization_value,
                record_owner_organization_id=organization_value,
            )
            .on_conflict_do_nothing(index_elements=[organizations_table.c.organization_id])
        )
        connection.execute(
            insert(bootstrap_receipts_table).values(
                bootstrap_receipt_id=uuid4(),
                record_owner_organization_id=organization_value,
                profile_code=BOOTSTRAP_PROFILE_CODE,
                profile_version=BOOTSTRAP_PROFILE_VERSION,
                environment=settings.environment,
                origin=BOOTSTRAP_ORIGIN,
                authority_actor_id=settings.authority_actor_id,
                applied_at=datetime.now(UTC),
                result=BootstrapResult.APLICADO.value,
            )
        )
    return BootstrapOutcome(BootstrapResult.APLICADO, settings.operator_organization_id)


def _required_uuid(source: Mapping[str, str], name: str) -> UUID:
    value = source.get(name)
    if not value:
        raise BootstrapConfigurationError(f"{name} não foi definida.")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise BootstrapConfigurationError(f"{name} deve conter UUID válido.") from error
    if parsed.int == 0:
        raise BootstrapConfigurationError(f"{name} não aceita UUID nulo.")
    return parsed
