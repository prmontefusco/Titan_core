"""Testes de recepção e revalidação de lotes offline (Passo 7.9).

Os cenários seguem a lista de testabilidade da ADR-0021: interrupção, duplicidade,
retomada, dependência, ciclo, relógio, quarentena e resultado desconhecido.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application.synchronization_service import (
    DeviceAdmission,
    OfficialEffectConflict,
    OfficialEffectRejected,
    OfficialEffectResultUnknown,
    SynchronizationService,
)
from packages.core_domain.events import CanonicalPayload
from packages.core_domain.synchronization import (
    DeviceClockReading,
    OfflineOperation,
    SynchronizationBatch,
    SynchronizationBatchResult,
    SynchronizationBatchState,
    SynchronizationConflictReason,
    SynchronizationResult,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

T0 = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


@dataclass
class FakeSynchronizationRepository:
    """Repositório em memória com a mesma semântica do PostgreSQL.

    Resultados são append-only por tentativa e `get_result` devolve a última,
    exatamente como a tabela real.
    """

    operations: dict[TypedId, OfflineOperation] = field(default_factory=dict)
    results: list[SynchronizationResult] = field(default_factory=list)
    batch_digests: dict[TypedId, str] = field(default_factory=dict)
    batch_attempts: dict[TypedId, int] = field(default_factory=dict)
    batch_results: list[SynchronizationBatchResult] = field(default_factory=list)
    arrival_order: list[TypedId] = field(default_factory=list)

    def get_batch_manifest_digest(self, batch_id: TypedId) -> str | None:
        return self.batch_digests.get(batch_id)

    def register_batch(self, batch: SynchronizationBatch, received_at: datetime) -> int:
        self.batch_digests.setdefault(batch.batch_id, batch.manifest_digest)
        attempt = self.batch_attempts.get(batch.batch_id, 0) + 1
        self.batch_attempts[batch.batch_id] = attempt
        return attempt

    def save_operation(self, operation: OfflineOperation) -> None:
        if operation.operation_id in self.operations:
            return
        self.operations[operation.operation_id] = operation
        self.arrival_order.append(operation.operation_id)

    def save_result(self, result: SynchronizationResult) -> None:
        self.results.append(result)

    def save_batch_result(self, batch_result: SynchronizationBatchResult) -> None:
        self.batch_results.append(batch_result)

    def get_result(self, operation_id: TypedId) -> SynchronizationResult | None:
        candidatos = [r for r in self.results if r.operation_id == operation_id]
        return max(candidatos, key=lambda r: r.attempt) if candidatos else None

    def find_by_idempotency_key(
        self, organization_id: OrganizationId, idempotency_key: str
    ) -> tuple[TypedId, str] | None:
        for operation_id in self.arrival_order:
            operation = self.operations[operation_id]
            if (
                operation.organization_id == organization_id
                and operation.idempotency_key == idempotency_key
            ):
                return (operation.operation_id, operation.intent_digest)
        return None


@dataclass
class RecordingEffect:
    """Handler de efeito oficial com comportamento programável por operação."""

    organization_id: OrganizationId
    applied: list[TypedId] = field(default_factory=list)
    behaviour: dict[TypedId, Exception] = field(default_factory=dict)

    def __call__(self, operation: OfflineOperation) -> tuple[UniversalReference, ...]:
        problema = self.behaviour.get(operation.operation_id)
        if problema is not None:
            raise problema
        self.applied.append(operation.operation_id)
        return (
            UniversalReference(
                target_id=TypedId.new("fact"),
                organization_id=self.organization_id,
                contract_version=1,
            ),
        )


@dataclass
class FixedAdmission:
    admission: DeviceAdmission

    def admit(
        self,
        organization_id: OrganizationId,
        device_reference: UniversalReference,
        at: datetime,
    ) -> DeviceAdmission:
        return self.admission


@dataclass
class Cenario:
    org: OrganizationId
    device: UniversalReference
    actor: UniversalReference
    repository: FakeSynchronizationRepository
    effect: RecordingEffect
    service: SynchronizationService

    def operation(
        self,
        *,
        key: str = "captura-0000001",
        identity: str = "operacao.captura:001",
        sequence: int = 1,
        depends_on: tuple[TypedId, ...] = (),
        conteudo: str = "registro",
        confidence: TimeConfidenceLevel = TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
        operation_id: TypedId | None = None,
    ) -> OfflineOperation:
        return OfflineOperation(
            operation_id=operation_id or TypedId.new("offline_operation"),
            organization_id=self.org,
            device_reference=self.device,
            actor_reference=self.actor,
            semantic_identity=identity,
            idempotency_key=key,
            operation_type="operacao.captura",
            contract_version=1,
            local_sequence=sequence,
            clock=DeviceClockReading(
                client_observed_at=T0,
                claimed_occurred_at=T0 - timedelta(minutes=10),
                timezone_name="America/Sao_Paulo",
                confidence=confidence,
                last_server_contact_at=(
                    T0 - timedelta(hours=1)
                    if confidence is TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR
                    else None
                ),
                monotonic_continuity_id=(
                    "boot-1" if confidence is TimeConfidenceLevel.MONOTONICO_LOCAL else ""
                ),
            ),
            payload=CanonicalPayload(
                schema="operacao.captura", version=1, value={"descricao": conteudo}
            ),
            depends_on=depends_on,
        )

    def batch(
        self, *operations: OfflineOperation, batch_id: TypedId | None = None
    ) -> SynchronizationBatch:
        return SynchronizationBatch.create(
            organization_id=self.org,
            device_reference=self.device,
            operations=operations,
            created_at_device=T0,
            batch_id=batch_id,
        )

    def send(
        self,
        batch: SynchronizationBatch,
        operations: tuple[OfflineOperation, ...],
        received_at: datetime = T0,
    ) -> SynchronizationBatchResult:
        return self.service.receive_batch(batch, operations, received_at)

    def result_for(self, operation: OfflineOperation) -> SynchronizationResult:
        stored = self.repository.get_result(operation.operation_id)
        assert stored is not None
        return stored


def _cenario(admission: DeviceAdmission = DeviceAdmission.PERMITIDO) -> Cenario:
    org = OrganizationId.new()
    repository = FakeSynchronizationRepository()
    effect = RecordingEffect(organization_id=org)
    return Cenario(
        org=org,
        device=UniversalReference(
            target_id=TypedId.new("device"), organization_id=org, contract_version=1
        ),
        actor=UniversalReference(
            target_id=TypedId.new("user"), organization_id=org, contract_version=1
        ),
        repository=repository,
        effect=effect,
        service=SynchronizationService(
            repository=repository,
            effect_handler=effect,
            device_admission=FixedAdmission(admission),
        ),
    )


@pytest.fixture
def cenario() -> Cenario:
    return _cenario()


class TestRecepcaoEstrutural:
    def test_lote_adulterado_nao_produz_nenhum_efeito(self, cenario: Cenario) -> None:
        original = cenario.operation()
        batch = cenario.batch(original)
        adulterada = cenario.operation(operation_id=original.operation_id, conteudo="trocado")

        resultado = cenario.send(batch, (adulterada,))

        assert resultado.state is SynchronizationBatchState.REJEITADO_ESTRUTURALMENTE
        assert resultado.examined_count == 0
        assert cenario.effect.applied == []
        assert any("DIGEST_DIVERGENTE" in limite for limite in resultado.limitations)

    def test_manifesto_alterado_entre_retomadas_e_recusado(self, cenario: Cenario) -> None:
        batch_id = TypedId.new("synchronization_batch")
        primeira = cenario.operation(key="captura-0000001", sequence=1)
        segunda = cenario.operation(key="captura-0000002", sequence=2)

        cenario.send(cenario.batch(primeira, segunda, batch_id=batch_id), (primeira, segunda))

        # Mesmo BatchId, manifesto diferente: aceitar substituiria capturas já enviadas.
        trocado = cenario.batch(primeira, batch_id=batch_id)
        resultado = cenario.send(trocado, (primeira,))

        assert resultado.state is SynchronizationBatchState.REJEITADO_ESTRUTURALMENTE
        assert any(
            SynchronizationConflictReason.MANIFESTO_DIVERGENTE_ENTRE_RETOMADAS.value in limite
            for limite in resultado.limitations
        )


class TestIdempotenciaERetomada:
    def test_mesma_operacao_reenviada_nao_repete_efeito(self, cenario: Cenario) -> None:
        operacao = cenario.operation()
        batch = cenario.batch(operacao)

        cenario.send(batch, (operacao,))
        cenario.send(batch, (operacao,), received_at=T0 + timedelta(minutes=5))

        assert cenario.effect.applied == [operacao.operation_id]
        recuperado = cenario.result_for(operacao)
        assert recuperado.status is SynchronizationResultStatus.ACEITA
        assert "RESULTADO_RECUPERADO" in recuperado.reason_codes
        assert recuperado.attempt == 2

    def test_recaptura_da_mesma_intencao_e_duplicada(self, cenario: Cenario) -> None:
        primeira = cenario.operation()
        cenario.send(cenario.batch(primeira), (primeira,))

        # Outro envelope, mesma chave e mesma intenção: o Device recapturou.
        recaptura = cenario.operation(sequence=2)
        resultado_lote = cenario.send(cenario.batch(recaptura), (recaptura,))

        assert cenario.effect.applied == [primeira.operation_id]
        duplicada = cenario.result_for(recaptura)
        assert duplicada.status is SynchronizationResultStatus.DUPLICADA
        assert duplicada.produced_references == cenario.result_for(primeira).produced_references
        assert resultado_lote.state is SynchronizationBatchState.PROCESSADO

    def test_mesma_chave_com_intencao_diferente_e_conflito(self, cenario: Cenario) -> None:
        primeira = cenario.operation(conteudo="pesagem")
        cenario.send(cenario.batch(primeira), (primeira,))

        divergente = cenario.operation(sequence=2, conteudo="abate")
        cenario.send(cenario.batch(divergente), (divergente,))

        conflitante = cenario.result_for(divergente)
        assert conflitante.status is SynchronizationResultStatus.CONFLITANTE
        assert conflitante.conflict is not None
        assert (
            conflitante.conflict.reason
            is SynchronizationConflictReason.IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE
        )
        # Nunca recupera nem associa o resultado anterior.
        assert conflitante.produced_references == ()
        assert cenario.effect.applied == [primeira.operation_id]

    def test_lote_parcialmente_aceito_retoma_sem_duplicar(self, cenario: Cenario) -> None:
        aceita = cenario.operation(key="captura-0000001", sequence=1)
        recusada = cenario.operation(
            key="captura-0000002", identity="operacao.captura:002", sequence=2
        )
        cenario.effect.behaviour[recusada.operation_id] = OfficialEffectRejected(
            "CAMPO_OBRIGATORIO_AUSENTE"
        )
        batch = cenario.batch(aceita, recusada)

        primeiro = cenario.send(batch, (aceita, recusada))
        assert primeiro.state is SynchronizationBatchState.PROCESSADO_PARCIALMENTE

        segundo = cenario.send(batch, (aceita, recusada), received_at=T0 + timedelta(minutes=1))

        assert cenario.effect.applied == [aceita.operation_id]
        assert segundo.counts[SynchronizationResultStatus.ACEITA] == 1
        assert cenario.result_for(recusada).status is SynchronizationResultStatus.REJEITADA

    def test_rejeicao_preserva_a_captura(self, cenario: Cenario) -> None:
        recusada = cenario.operation()
        cenario.effect.behaviour[recusada.operation_id] = OfficialEffectRejected("FORA_DE_PRAZO")

        cenario.send(cenario.batch(recusada), (recusada,))

        assert recusada.operation_id in cenario.repository.operations
        resultado = cenario.result_for(recusada)
        assert resultado.status is SynchronizationResultStatus.REJEITADA
        assert resultado.reason_codes == ("FORA_DE_PRAZO",)


class TestDependencias:
    def test_ordem_fisica_nao_cria_causalidade(self, cenario: Cenario) -> None:
        origem = cenario.operation(key="captura-0000001", sequence=1)
        dependente = cenario.operation(
            key="captura-0000002",
            identity="operacao.captura:002",
            sequence=2,
            depends_on=(origem.operation_id,),
        )
        # A dependente vem fisicamente antes da origem no lote.
        batch = cenario.batch(dependente, origem)

        resultado = cenario.send(batch, (dependente, origem))

        assert resultado.state is SynchronizationBatchState.PROCESSADO
        assert cenario.effect.applied == [origem.operation_id, dependente.operation_id]

    def test_dependencia_ausente_fica_pendente_e_destrava_na_retomada(
        self, cenario: Cenario
    ) -> None:
        origem_id = TypedId.new("offline_operation")
        dependente = cenario.operation(
            key="captura-0000002",
            identity="operacao.captura:002",
            sequence=2,
            depends_on=(origem_id,),
        )

        cenario.send(cenario.batch(dependente), (dependente,))
        pendente = cenario.result_for(dependente)
        assert pendente.status is SynchronizationResultStatus.DEPENDENCIA_PENDENTE
        assert pendente.pending_dependencies == (origem_id,)
        assert "DEPENDENCIA_DESCONHECIDA" in pendente.reason_codes
        assert cenario.effect.applied == []

        origem = cenario.operation(key="captura-0000001", sequence=1, operation_id=origem_id)
        cenario.send(cenario.batch(origem), (origem,), received_at=T0 + timedelta(minutes=1))
        cenario.send(
            cenario.batch(dependente), (dependente,), received_at=T0 + timedelta(minutes=2)
        )

        assert cenario.result_for(dependente).status is SynchronizationResultStatus.ACEITA

    def test_dependencia_rejeitada_permanece_explicita(self, cenario: Cenario) -> None:
        origem = cenario.operation(key="captura-0000001", sequence=1)
        cenario.effect.behaviour[origem.operation_id] = OfficialEffectRejected("INVALIDA")
        dependente = cenario.operation(
            key="captura-0000002",
            identity="operacao.captura:002",
            sequence=2,
            depends_on=(origem.operation_id,),
        )

        cenario.send(cenario.batch(origem, dependente), (origem, dependente))

        resultado = cenario.result_for(dependente)
        assert resultado.status is SynchronizationResultStatus.DEPENDENCIA_PENDENTE
        # Dependência recusada não é tratada como inexistente.
        assert "DEPENDENCIA_REJEITADA" in resultado.reason_codes

    def test_ciclo_vira_conflito_e_nao_pendencia_indefinida(self, cenario: Cenario) -> None:
        primeira_id = TypedId.new("offline_operation")
        segunda_id = TypedId.new("offline_operation")
        primeira = cenario.operation(
            key="captura-0000001", sequence=1, operation_id=primeira_id, depends_on=(segunda_id,)
        )
        segunda = cenario.operation(
            key="captura-0000002",
            identity="operacao.captura:002",
            sequence=2,
            operation_id=segunda_id,
            depends_on=(primeira_id,),
        )

        cenario.send(cenario.batch(primeira, segunda), (primeira, segunda))

        for operacao in (primeira, segunda):
            resultado = cenario.result_for(operacao)
            assert resultado.status is SynchronizationResultStatus.CONFLITANTE
            assert resultado.conflict is not None
            assert resultado.conflict.reason is SynchronizationConflictReason.DEPENDENCIA_CICLICA
        assert cenario.effect.applied == []


class TestRelogioEDevice:
    def test_relogio_indeterminado_gera_conflito(self, cenario: Cenario) -> None:
        operacao = cenario.operation(confidence=TimeConfidenceLevel.INDETERMINADO)

        cenario.send(cenario.batch(operacao), (operacao,))

        resultado = cenario.result_for(operacao)
        assert resultado.status is SynchronizationResultStatus.CONFLITANTE
        assert resultado.conflict is not None
        assert resultado.conflict.reason is SynchronizationConflictReason.RELOGIO_INSUFICIENTE
        assert cenario.effect.applied == []

    def test_device_bloqueado_coloca_operacao_em_quarentena(self) -> None:
        cenario = _cenario(admission=DeviceAdmission.BLOQUEADO)
        operacao = cenario.operation()

        cenario.send(cenario.batch(operacao), (operacao,))

        resultado = cenario.result_for(operacao)
        assert resultado.status is SynchronizationResultStatus.EM_QUARENTENA
        assert resultado.reason_codes == ("DEVICE_BLOQUEADO",)
        # A captura é preservada mesmo sem efeito.
        assert operacao.operation_id in cenario.repository.operations
        assert cenario.effect.applied == []


class TestResultadoDesconhecido:
    def test_falha_apos_o_commit_produz_desconhecido_com_prazo(self, cenario: Cenario) -> None:
        operacao = cenario.operation()
        cenario.effect.behaviour[operacao.operation_id] = OfficialEffectResultUnknown(
            "Conexão perdida após o commit e antes da resposta."
        )

        resultado_lote = cenario.send(cenario.batch(operacao), (operacao,))

        resultado = cenario.result_for(operacao)
        assert resultado.status is SynchronizationResultStatus.RESULTADO_DESCONHECIDO
        assert resultado.reconciliation_deadline == T0 + timedelta(hours=24)
        assert resultado_lote.state is SynchronizationBatchState.RESULTADO_INDETERMINADO

    def test_reenvio_nao_converte_desconhecido_em_sucesso(self, cenario: Cenario) -> None:
        operacao = cenario.operation()
        cenario.effect.behaviour[operacao.operation_id] = OfficialEffectResultUnknown(
            "Resposta perdida."
        )
        batch = cenario.batch(operacao)
        cenario.send(batch, (operacao,))

        # Mesmo com o efeito voltando a funcionar, reprocessar poderia duplicar.
        del cenario.effect.behaviour[operacao.operation_id]
        cenario.send(batch, (operacao,), received_at=T0 + timedelta(minutes=1))

        assert cenario.effect.applied == []
        assert (
            cenario.result_for(operacao).status
            is SynchronizationResultStatus.RESULTADO_DESCONHECIDO
        )


class TestConflitoDeEstado:
    def test_conflito_de_versao_nao_e_resolvido_por_last_write_wins(self, cenario: Cenario) -> None:
        operacao = cenario.operation()
        cenario.effect.behaviour[operacao.operation_id] = OfficialEffectConflict(
            SynchronizationConflictReason.VERSAO_DIVERGENTE,
            "A versão esperada do agregado já avançou no servidor.",
            ("Reenviar sobre a versão atual.", "Registrar Correction autorizada."),
        )

        cenario.send(cenario.batch(operacao), (operacao,))

        resultado = cenario.result_for(operacao)
        assert resultado.status is SynchronizationResultStatus.CONFLITANTE
        assert resultado.conflict is not None
        assert resultado.conflict.reason is SynchronizationConflictReason.VERSAO_DIVERGENTE
        # O conflito exige alternativas explícitas; nada é decidido em silêncio.
        assert resultado.conflict.alternatives
        assert cenario.effect.applied == []
