"""Testes de integração PostgreSQL com RLS para sincronização offline (Passo 7.9)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import IntegrityError

from packages.core_application.synchronization_service import (
    OfficialEffectRejected,
    SynchronizationService,
)
from packages.core_domain.events import CanonicalPayload
from packages.core_domain.synchronization import (
    DeviceClockReading,
    OfflineOperation,
    SynchronizationBatch,
    SynchronizationBatchState,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
)
from packages.core_infrastructure.persistence.synchronization import (
    TransactionalSynchronizationRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

T0 = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def _ref(org: OrganizationId, entity_type: str) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org, contract_version=1
    )


def _operation(
    org: OrganizationId,
    device: UniversalReference,
    actor: UniversalReference,
    *,
    key: str,
    identity: str,
    sequence: int,
    depends_on: tuple[TypedId, ...] = (),
    conteudo: str = "registro",
) -> OfflineOperation:
    return OfflineOperation(
        operation_id=TypedId.new("offline_operation"),
        organization_id=org,
        device_reference=device,
        actor_reference=actor,
        semantic_identity=identity,
        idempotency_key=key,
        operation_type="operacao.captura",
        contract_version=1,
        local_sequence=sequence,
        clock=DeviceClockReading(
            client_observed_at=T0,
            claimed_occurred_at=T0 - timedelta(minutes=15),
            timezone_name="America/Sao_Paulo",
            confidence=TimeConfidenceLevel.MONOTONICO_LOCAL,
            monotonic_continuity_id="boot-1",
            monotonic_elapsed_ms=sequence * 1000,
        ),
        payload=CanonicalPayload(
            schema="operacao.captura", version=1, value={"descricao": conteudo}
        ),
        depends_on=depends_on,
    )


def _create_organizations(connection: Connection, *organizations: OrganizationId) -> None:
    for organization in organizations:
        connection.execute(
            text(
                """
                INSERT INTO core_identity.organizations
                (organization_id, record_owner_organization_id)
                VALUES (:id, :id)
                """
            ),
            {"id": organization.value},
        )


def _set_context(connection: Connection, organization: OrganizationId) -> None:
    connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(organization.value)},
    )


def test_sincronizacao_completa_com_retomada_e_isolamento(db_connection: Connection) -> None:
    org_1 = OrganizationId.new()
    org_2 = OrganizationId.new()
    _create_organizations(db_connection, org_1, org_2)
    _set_context(db_connection, org_1)

    device = _ref(org_1, "device")
    actor = _ref(org_1, "user")
    repository = TransactionalSynchronizationRepository(connection=db_connection)

    aplicadas: list[TypedId] = []
    recusar: set[TypedId] = set()

    def efeito(operation: OfflineOperation) -> tuple[UniversalReference, ...]:
        if operation.operation_id in recusar:
            raise OfficialEffectRejected("CAMPO_OBRIGATORIO_AUSENTE")
        aplicadas.append(operation.operation_id)
        return (_ref(org_1, "fact"),)

    service = SynchronizationService(repository=repository, effect_handler=efeito)

    origem = _operation(
        org_1, device, actor, key="captura-0000001", identity="operacao.captura:001", sequence=1
    )
    dependente = _operation(
        org_1,
        device,
        actor,
        key="captura-0000002",
        identity="operacao.captura:002",
        sequence=2,
        depends_on=(origem.operation_id,),
    )
    recusada = _operation(
        org_1, device, actor, key="captura-0000003", identity="operacao.captura:003", sequence=3
    )
    recusar.add(recusada.operation_id)

    # A dependente vem fisicamente primeiro: ordem física não é causalidade.
    batch = SynchronizationBatch.create(
        organization_id=org_1,
        device_reference=device,
        operations=(dependente, origem, recusada),
        created_at_device=T0,
    )
    primeiro = service.receive_batch(batch, (dependente, origem, recusada), T0)

    assert primeiro.state is SynchronizationBatchState.PROCESSADO_PARCIALMENTE
    assert primeiro.counts[SynchronizationResultStatus.ACEITA] == 2
    assert primeiro.counts[SynchronizationResultStatus.REJEITADA] == 1
    assert aplicadas == [origem.operation_id, dependente.operation_id]

    # Retomada do mesmo lote: nenhum efeito é repetido.
    segundo = service.receive_batch(
        batch, (dependente, origem, recusada), T0 + timedelta(minutes=3)
    )
    assert aplicadas == [origem.operation_id, dependente.operation_id]
    assert segundo.counts[SynchronizationResultStatus.ACEITA] == 2

    recuperado = repository.get_result(origem.operation_id)
    assert recuperado is not None
    assert recuperado.status is SynchronizationResultStatus.ACEITA
    assert recuperado.attempt == 2
    assert "RESULTADO_RECUPERADO" in recuperado.reason_codes

    # A captura recusada continua preservada e auditável.
    armazenada = repository.get_operation(recusada.operation_id)
    assert armazenada is not None
    assert armazenada.intent_digest == recusada.intent_digest
    assert armazenada.payload_canonical_bytes == recusada.payload.canonical_bytes

    # Histórico append-only: as duas tentativas coexistem.
    tentativas = db_connection.execute(
        text(
            """
            SELECT attempt, status
            FROM core_audit.synchronization_results
            WHERE operation_id = :operation_id
            ORDER BY attempt
            """
        ),
        {"operation_id": origem.operation_id.value},
    ).fetchall()
    assert [linha.attempt for linha in tentativas] == [1, 2]

    # Isolamento: uma role sem BYPASSRLS na outra Organization não enxerga nada.
    role_name = f"titan_rls_sync_{uuid4().hex[:12]}"
    quoted_role = f'"{role_name}"'
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for tabela in (
        "offline_operations",
        "synchronization_results",
        "synchronization_batches",
    ):
        db_connection.execute(text(f"GRANT SELECT ON core_audit.{tabela} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    _set_context(db_connection, org_2)

    visiveis = TransactionalSynchronizationRepository(connection=db_connection)
    assert visiveis.get_operation(origem.operation_id) is None
    assert visiveis.get_result(origem.operation_id) is None
    assert visiveis.get_batch_manifest_digest(batch.batch_id) is None
    assert visiveis.find_by_idempotency_key(org_1, origem.idempotency_key) is None

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))


def test_banco_recusa_aceitacao_sem_efeito_e_conflito_mudo(db_connection: Connection) -> None:
    """As invariantes do domínio também valem para escrita direta em SQL."""
    org = OrganizationId.new()
    _create_organizations(db_connection, org)
    _set_context(db_connection, org)

    def _inserir(status: str) -> None:
        db_connection.execute(
            text(
                """
                INSERT INTO core_audit.synchronization_results (
                    operation_id, attempt, record_owner_organization_id, batch_id,
                    status, decided_at
                ) VALUES (
                    :operation_id, 1, :org_id, :batch_id, :status, :decided_at
                )
                """
            ),
            {
                "operation_id": uuid4(),
                "org_id": org.value,
                "batch_id": uuid4(),
                "status": status,
                "decided_at": T0,
            },
        )

    # O savepoint precisa envolver o `raises`, e não o contrário: a violação
    # aborta a transação, e só o rollback até o savepoint permite continuar.
    for status, constraint in (
        ("ACEITA", "ck_synchronization_results_efeito"),
        ("CONFLITANTE", "ck_synchronization_results_conflict"),
        ("RESULTADO_DESCONHECIDO", "ck_synchronization_results_reconciliation"),
    ):
        with pytest.raises(IntegrityError, match=constraint):
            with db_connection.begin_nested():
                _inserir(status)
