"""Ambiente Alembic do PostgreSQL autoritativo do Titan."""

from collections.abc import MutableMapping
from logging.config import fileConfig
from typing import Literal

from alembic import context

from packages.core_infrastructure.bootstrap import bootstrap_receipts_table
from packages.core_infrastructure.persistence import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.checkpoints import integrity_checkpoints_table
from packages.core_infrastructure.persistence.crypto import key_registry_table
from packages.core_infrastructure.persistence.decision import decisions_table
from packages.core_infrastructure.persistence.dossier import dossiers_table
from packages.core_infrastructure.persistence.evaluation import evaluations_table
from packages.core_infrastructure.persistence.events import (
    CORE_AUDIT_SCHEMA,
    domain_events_table,
    event_integrity_table,
)
from packages.core_infrastructure.persistence.evidence import (
    attachments_table,
    evidence_verifications_table,
    evidences_table,
)
from packages.core_infrastructure.persistence.external_identities import external_identities_table
from packages.core_infrastructure.persistence.idempotency import idempotency_records_table
from packages.core_infrastructure.persistence.nonconformity import nonconformities_table
from packages.core_infrastructure.persistence.organizations import (
    CORE_IDENTITY_SCHEMA,
)
from packages.core_infrastructure.persistence.outbox import (
    outbox_messages_table,
    outbox_publication_attempts_table,
    outbox_publication_state_table,
)
from packages.core_infrastructure.persistence.policy import policies_table
from packages.core_infrastructure.persistence.projections import reference_projection_table
from packages.core_infrastructure.persistence.recall import recalls_table
from packages.core_infrastructure.persistence.relations import relations_table
from packages.core_infrastructure.persistence.rule import rules_table
from packages.core_infrastructure.persistence.synchronization import (
    offline_operations_table,
    synchronization_batches_table,
    synchronization_results_table,
)
from packages.core_infrastructure.persistence.timestamping import timestamp_attempts_table
from packages.livestock_infrastructure.persistence import (
    animal_identifiers_table,
    animal_movement_items_table,
    animal_movements_table,
    animals_table,
    livestock_lots_table,
    lot_memberships_table,
    medication_batches_table,
    medications_table,
    prescription_targets_table,
    prescriptions_table,
    property_stays_table,
    rural_properties_table,
    veterinarians_table,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = external_identities_table.metadata

# O import registra a tabela no mesmo MetaData compartilhado usado pelo Alembic.
assert bootstrap_receipts_table.metadata is target_metadata
assert domain_events_table.metadata is target_metadata
assert event_integrity_table.metadata is target_metadata
assert integrity_checkpoints_table.metadata is target_metadata
assert idempotency_records_table.metadata is target_metadata
assert outbox_messages_table.metadata is target_metadata
assert outbox_publication_attempts_table.metadata is target_metadata
assert outbox_publication_state_table.metadata is target_metadata
assert timestamp_attempts_table.metadata is target_metadata
assert evidences_table.metadata is target_metadata
assert evidence_verifications_table.metadata is target_metadata
assert key_registry_table.metadata is target_metadata
assert attachments_table.metadata is target_metadata
assert policies_table.metadata is target_metadata
assert rules_table.metadata is target_metadata
assert evaluations_table.metadata is target_metadata
assert decisions_table.metadata is target_metadata
assert relations_table.metadata is target_metadata
assert reference_projection_table.metadata is target_metadata
assert nonconformities_table.metadata is target_metadata
assert recalls_table.metadata is target_metadata
assert dossiers_table.metadata is target_metadata
assert offline_operations_table.metadata is target_metadata
assert synchronization_results_table.metadata is target_metadata
assert synchronization_batches_table.metadata is target_metadata

# A vertical Livestock reusa a MetaData do Core (ver livestock .../metadata.py):
# suas tabelas têm FK para core_identity.organizations, e o SQLAlchemy só resolve
# a FK quando as duas tabelas estão na mesma MetaData. Importá-las aqui basta para
# registrá-las; o schema core_audit é declarado tabela a tabela.
assert rural_properties_table.metadata is target_metadata
assert animals_table.metadata is target_metadata
assert animal_identifiers_table.metadata is target_metadata
assert animal_movements_table.metadata is target_metadata
assert animal_movement_items_table.metadata is target_metadata
assert property_stays_table.metadata is target_metadata
assert livestock_lots_table.metadata is target_metadata
assert lot_memberships_table.metadata is target_metadata
assert veterinarians_table.metadata is target_metadata
assert medications_table.metadata is target_metadata
assert medication_batches_table.metadata is target_metadata
assert prescriptions_table.metadata is target_metadata
assert prescription_targets_table.metadata is target_metadata

MANAGED_SCHEMAS = frozenset({CORE_IDENTITY_SCHEMA, CORE_AUDIT_SCHEMA})


def include_managed_schema(
    name: str | None,
    type_: Literal[
        "schema",
        "table",
        "column",
        "index",
        "unique_constraint",
        "foreign_key_constraint",
    ],
    parent_names: MutableMapping[
        Literal["schema_name", "table_name", "schema_qualified_table_name"],
        str | None,
    ],
) -> bool:
    """Limita autogeração aos schemas que pertencem ao Titan."""
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    if type_ == "table":
        return parent_names.get("schema_name") in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    """Gera SQL sem estabelecer conexão."""

    settings = DatabaseSettings.from_environment()
    context.configure(
        url=settings.url,
        target_metadata=target_metadata,
        include_name=include_managed_schema,
        include_schemas=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations em uma transação PostgreSQL."""

    settings = DatabaseSettings.from_environment()
    engine = create_database_engine(settings)

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_name=include_managed_schema,
                include_schemas=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
