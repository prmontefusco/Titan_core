"""Ambiente Alembic próprio da vertical Titan Asset & Sustainment.

`script_location`, histórico de `versions/` e rastreamento de versão
(`alembic_version_asset`) são independentes do ambiente de Core+Livestock em
`packages/core_infrastructure/persistence/migrations/` — Opção D -> C de
`docs/architecture/MIGRATION_CONCURRENCY_STRATEGY.md`, passo A-M1. Os dois
ambientes aplicam contra o mesmo banco físico; usar a mesma tabela de rastreio
faria um sobrescrever o ponteiro do outro, por isso a tabela própria.

Reusa a `MetaData` do Core (`organization_metadata`) porque as tabelas de Asset
têm FK para `core_identity.organizations` — o SQLAlchemy só resolve a FK quando
as duas tabelas estão na mesma MetaData (mesmo motivo de
`packages/livestock_infrastructure/persistence/metadata.py`).

`include_object` filtra a autogeração por `titan.module_owner=asset` (mais a
allowlist de FK do Core) via `make_include_object` — não por schema, já que
Asset e Livestock dividem o schema `core_audit` (`module_owner.py`).

Invocar com:
    alembic -c packages/asset_infrastructure/persistence/migrations/alembic.ini <comando>
"""

from logging.config import fileConfig

from alembic import context

from packages.asset_infrastructure.persistence import (
    applicability_table,
    configuration_baseline_positions_table,
    configuration_baselines_table,
    contract_version_coverage_lines_table,
    contract_versions_table,
    customer_site_contacts_table,
    customer_sites_table,
    interchangeability_group_members_table,
    interchangeability_groups_table,
    part_revisions_table,
    part_supersessions_table,
    parts_table,
    sli_contracts_table,
    stock_locations_table,
    stock_position_reservations_table,
    stock_positions_table,
    stock_reservations_table,
    stock_transfers_table,
    vehicle_meter_corrections_table,
    vehicle_meter_readings_table,
    vehicles_table,
)
from packages.core_infrastructure.bootstrap import bootstrap_receipts_table
from packages.core_infrastructure.persistence import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.authorization_grant import authorization_grants_table
from packages.core_infrastructure.persistence.checkpoints import integrity_checkpoints_table
from packages.core_infrastructure.persistence.crypto import key_registry_table
from packages.core_infrastructure.persistence.database import (
    MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE,
)
from packages.core_infrastructure.persistence.decision import decisions_table
from packages.core_infrastructure.persistence.decision_governance import (
    decision_authority_profiles_table,
    decision_contestations_table,
    decision_overrides_table,
    decision_proposals_table,
    decision_reviews_table,
)
from packages.core_infrastructure.persistence.dossier import dossiers_table
from packages.core_infrastructure.persistence.evaluation import evaluations_table
from packages.core_infrastructure.persistence.events import (
    domain_events_table,
    event_integrity_table,
)
from packages.core_infrastructure.persistence.evidence import (
    attachments_table,
    evidence_revocations_table,
    evidence_signatures_table,
    evidence_verifications_table,
    evidences_table,
)
from packages.core_infrastructure.persistence.external_identities import external_identities_table
from packages.core_infrastructure.persistence.idempotency import idempotency_records_table
from packages.core_infrastructure.persistence.migrations.module_owner import (
    make_include_object,
)
from packages.core_infrastructure.persistence.nonconformity import nonconformities_table
from packages.core_infrastructure.persistence.organizations import organization_metadata
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
from packages.core_infrastructure.persistence.rule_governance import (
    rule_adoptions_table,
    rule_identities_table,
    rule_timeline_events_table,
)
from packages.core_infrastructure.persistence.shared_decision import shared_decisions_table
from packages.core_infrastructure.persistence.shared_policy_access_log import (
    shared_policy_access_log_table,
)
from packages.core_infrastructure.persistence.synchronization import (
    offline_operations_table,
    synchronization_batches_table,
    synchronization_results_table,
)
from packages.core_infrastructure.persistence.timestamping import timestamp_attempts_table

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = organization_metadata

# O grafo de FK da MetaData compartilhada precisa estar completo antes que o
# Alembic possa ordenar/filtrar tabelas (`sorted_tables` roda antes de
# `include_object`) — por isso este env.py importa as mesmas tabelas do Core
# que `core_infrastructure/persistence/migrations/env.py` importa (elas não
# são "gerenciadas" por este ambiente; `include_object` as exclui da
# autogeração via `fk_allowlist`/module_owner). Tabelas de Livestock ficam de
# fora: nada aqui referencia uma FK para elas.
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
assert evidence_signatures_table.metadata is target_metadata
assert evidence_revocations_table.metadata is target_metadata
assert key_registry_table.metadata is target_metadata
assert attachments_table.metadata is target_metadata
assert policies_table.metadata is target_metadata
assert authorization_grants_table.metadata is target_metadata
assert rules_table.metadata is target_metadata
assert rule_identities_table.metadata is target_metadata
assert rule_timeline_events_table.metadata is target_metadata
assert rule_adoptions_table.metadata is target_metadata
assert evaluations_table.metadata is target_metadata
assert decisions_table.metadata is target_metadata
assert decision_authority_profiles_table.metadata is target_metadata
assert decision_proposals_table.metadata is target_metadata
assert decision_reviews_table.metadata is target_metadata
assert decision_overrides_table.metadata is target_metadata
assert decision_contestations_table.metadata is target_metadata
assert relations_table.metadata is target_metadata
assert reference_projection_table.metadata is target_metadata
assert nonconformities_table.metadata is target_metadata
assert recalls_table.metadata is target_metadata
assert dossiers_table.metadata is target_metadata
assert offline_operations_table.metadata is target_metadata
assert synchronization_results_table.metadata is target_metadata
assert synchronization_batches_table.metadata is target_metadata
assert shared_decisions_table.metadata is target_metadata
assert shared_policy_access_log_table.metadata is target_metadata
assert external_identities_table.metadata is target_metadata

# Tabelas de Asset (cresce incrementalmente, um agregado por vez):
assert customer_sites_table.metadata is target_metadata
assert customer_site_contacts_table.metadata is target_metadata
assert stock_locations_table.metadata is target_metadata
assert interchangeability_groups_table.metadata is target_metadata
assert parts_table.metadata is target_metadata
assert part_revisions_table.metadata is target_metadata
assert part_supersessions_table.metadata is target_metadata
assert interchangeability_group_members_table.metadata is target_metadata
assert applicability_table.metadata is target_metadata
assert configuration_baselines_table.metadata is target_metadata
assert configuration_baseline_positions_table.metadata is target_metadata
assert vehicles_table.metadata is target_metadata
assert vehicle_meter_readings_table.metadata is target_metadata
assert vehicle_meter_corrections_table.metadata is target_metadata
assert stock_positions_table.metadata is target_metadata
assert stock_reservations_table.metadata is target_metadata
assert stock_transfers_table.metadata is target_metadata
assert stock_position_reservations_table.metadata is target_metadata
assert sli_contracts_table.metadata is target_metadata
assert contract_versions_table.metadata is target_metadata
assert contract_version_coverage_lines_table.metadata is target_metadata

VERSION_TABLE = "alembic_version_asset"

include_object = make_include_object(
    owned_tokens={"asset"},
    fk_allowlist={("core_identity", "organizations")},
)


def run_migrations_offline() -> None:
    """Gera SQL sem estabelecer conexão."""

    settings = DatabaseSettings.from_environment(
        variable_name=MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE
    )
    context.configure(
        url=settings.url,
        target_metadata=target_metadata,
        include_object=include_object,
        include_schemas=True,
        version_table=VERSION_TABLE,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations em uma transação PostgreSQL."""

    settings = DatabaseSettings.from_environment(
        variable_name=MIGRATION_DATABASE_URL_ENVIRONMENT_VARIABLE
    )
    engine = create_database_engine(settings)

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                include_schemas=True,
                version_table=VERSION_TABLE,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
