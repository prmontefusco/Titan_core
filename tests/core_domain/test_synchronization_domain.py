"""Testes dos contratos de operação offline e sincronização (Passo 7.9)."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core_domain.events import CanonicalPayload
from packages.core_domain.synchronization import (
    BatchStructuralDefect,
    DeviceClockReading,
    OfflineOperation,
    OperationManifestEntry,
    SynchronizationBatch,
    SynchronizationBatchResult,
    SynchronizationBatchState,
    SynchronizationConflict,
    SynchronizationConflictReason,
    SynchronizationResult,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
    compute_manifest_digest,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference

T0 = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def _ref(org: OrganizationId, entity_type: str) -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org, contract_version=1
    )


def _clock(
    confidence: TimeConfidenceLevel = TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
    **overrides: object,
) -> DeviceClockReading:
    defaults: dict[str, object] = {
        "client_observed_at": T0,
        "claimed_occurred_at": T0 - timedelta(minutes=30),
        "timezone_name": "America/Sao_Paulo",
        "confidence": confidence,
        "last_server_contact_at": T0 - timedelta(hours=2),
    }
    defaults.update(overrides)
    return DeviceClockReading(**defaults)  # type: ignore[arg-type]


def _payload(value: str = "registro") -> CanonicalPayload:
    return CanonicalPayload(schema="operacao.captura", version=1, value={"descricao": value})


def _operation(
    org: OrganizationId,
    device: UniversalReference,
    actor: UniversalReference,
    *,
    key: str = "captura-0000001",
    identity: str = "operacao.captura:001",
    sequence: int = 1,
    depends_on: tuple[TypedId, ...] = (),
    payload: CanonicalPayload | None = None,
    clock: DeviceClockReading | None = None,
    operation_id: TypedId | None = None,
) -> OfflineOperation:
    return OfflineOperation(
        operation_id=operation_id or TypedId.new("offline_operation"),
        organization_id=org,
        device_reference=device,
        actor_reference=actor,
        semantic_identity=identity,
        idempotency_key=key,
        operation_type="operacao.captura",
        contract_version=1,
        local_sequence=sequence,
        clock=clock or _clock(),
        payload=payload or _payload(),
        depends_on=depends_on,
    )


@pytest.fixture
def contexto() -> tuple[OrganizationId, UniversalReference, UniversalReference]:
    org = OrganizationId.new()
    return org, _ref(org, "device"), _ref(org, "user")


class TestDeviceClockReading:
    def test_exige_representacao_utc(self) -> None:
        with pytest.raises(ValueError, match="timezone explícito"):
            _clock(client_observed_at=datetime(2026, 7, 22, 12, 0))

    def test_sincronizado_exige_contato_com_servidor(self) -> None:
        with pytest.raises(ValueError, match="último contato"):
            _clock(
                TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
                last_server_contact_at=None,
            )

    def test_monotonico_exige_continuidade_declarada(self) -> None:
        with pytest.raises(ValueError, match="continuidade monotônica"):
            _clock(TimeConfidenceLevel.MONOTONICO_LOCAL, last_server_contact_at=None)

    def test_medida_monotonica_sem_continuidade_nao_ordena(self) -> None:
        with pytest.raises(ValueError, match="monotonic_continuity_id"):
            _clock(monotonic_elapsed_ms=10)

    def test_ordem_relativa_existe_apenas_dentro_da_continuidade(self) -> None:
        primeira = _clock(
            TimeConfidenceLevel.MONOTONICO_LOCAL,
            monotonic_continuity_id="boot-a",
            monotonic_elapsed_ms=100,
            last_server_contact_at=None,
        )
        segunda = _clock(
            TimeConfidenceLevel.MONOTONICO_LOCAL,
            monotonic_continuity_id="boot-a",
            monotonic_elapsed_ms=900,
            last_server_contact_at=None,
        )
        outra_continuidade = _clock(
            TimeConfidenceLevel.MONOTONICO_LOCAL,
            monotonic_continuity_id="boot-b",
            monotonic_elapsed_ms=50,
            last_server_contact_at=None,
        )

        assert primeira.precedes(segunda) is True
        assert segunda.precedes(primeira) is False
        # Continuidade perdida não produz precedência: o relógio civil do Device
        # não substitui ordem global.
        assert primeira.precedes(outra_continuidade) is None


class TestOfflineOperation:
    def test_digest_da_intencao_ignora_envelope(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        primeira = _operation(org, device, actor, sequence=1)
        # Mesma intenção recapturada: outro OperationId, outra sequência, outro
        # relógio. O digest precisa continuar igual, senão o retry duplicaria.
        segunda = _operation(
            org,
            device,
            actor,
            sequence=7,
            clock=_clock(
                TimeConfidenceLevel.APENAS_RELOGIO_LOCAL,
                last_server_contact_at=None,
                client_observed_at=T0 + timedelta(hours=5),
            ),
        )

        assert primeira.operation_id != segunda.operation_id
        assert primeira.intent_digest == segunda.intent_digest

    def test_conteudo_diferente_muda_o_digest(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        assert (
            _operation(org, device, actor).intent_digest
            != _operation(org, device, actor, payload=_payload("outro")).intent_digest
        )

    def test_recusa_referencia_de_outra_organization(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, _ = contexto
        estrangeiro = _ref(OrganizationId.new(), "user")
        with pytest.raises(ValueError, match="pertencer à Organization"):
            _operation(org, device, estrangeiro)

    def test_recusa_dependencia_de_si_mesma(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        operation_id = TypedId.new("offline_operation")
        with pytest.raises(ValueError, match="depender de si mesma"):
            _operation(org, device, actor, operation_id=operation_id, depends_on=(operation_id,))

    def test_recusa_credencial_no_conteudo(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        with pytest.raises(ValueError, match="segredo ou credencial"):
            _operation(
                org,
                device,
                actor,
                payload=CanonicalPayload(
                    schema="operacao.captura", version=1, value={"password": "x"}
                ),
            )

    def test_recusa_identidade_semantica_sem_discriminador(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        with pytest.raises(ValueError, match="semantic_identity"):
            _operation(org, device, actor, identity="operacao.captura")


class TestSynchronizationBatch:
    def test_manifesto_detecta_alteracao_de_operacao(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        original = _operation(org, device, actor)
        batch = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(original,),
            created_at_device=T0,
        )

        adulterada = _operation(
            org,
            device,
            actor,
            operation_id=original.operation_id,
            payload=_payload("conteudo trocado"),
        )
        defeitos = dict(batch.inspect((adulterada,)))
        assert BatchStructuralDefect.DIGEST_DIVERGENTE in defeitos

    def test_manifesto_detecta_remocao_e_substituicao(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        primeira = _operation(org, device, actor, key="captura-0000001", sequence=1)
        segunda = _operation(org, device, actor, key="captura-0000002", sequence=2)
        batch = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(primeira, segunda),
            created_at_device=T0,
        )

        intrusa = _operation(org, device, actor, key="captura-0000003", sequence=2)
        defeitos = dict(batch.inspect((primeira, intrusa)))
        assert BatchStructuralDefect.OPERACAO_AUSENTE in defeitos
        assert BatchStructuralDefect.OPERACAO_NAO_DECLARADA in defeitos

    def test_digest_do_manifesto_muda_com_a_ordem_fisica(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        primeira = _operation(org, device, actor, key="captura-0000001", sequence=1)
        segunda = _operation(org, device, actor, key="captura-0000002", sequence=2)

        direta = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(primeira, segunda),
            created_at_device=T0,
        )
        invertida = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(segunda, primeira),
            created_at_device=T0,
        )
        assert direta.manifest_digest != invertida.manifest_digest

    def test_recusa_manifesto_adulterado_sem_recalcular_digest(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        operation = _operation(org, device, actor)
        manifesto = (
            OperationManifestEntry(
                operation_id=operation.operation_id,
                semantic_identity=operation.semantic_identity,
                intent_digest=operation.intent_digest,
                position=0,
            ),
        )
        with pytest.raises(ValueError, match="manifest_digest"):
            SynchronizationBatch(
                batch_id=TypedId.new("synchronization_batch"),
                batch_version=1,
                organization_id=org,
                device_reference=device,
                manifest=manifesto,
                operation_count=1,
                manifest_digest="0" * 64,
                sequence_boundary=(1, 1),
                created_at_device=T0,
            )

    def test_operacao_fora_da_fronteira_de_sequencia(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        declarada = _operation(org, device, actor, sequence=5)
        batch = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(declarada,),
            created_at_device=T0,
        )
        fora = OfflineOperation(
            operation_id=declarada.operation_id,
            organization_id=org,
            device_reference=device,
            actor_reference=actor,
            semantic_identity=declarada.semantic_identity,
            idempotency_key=declarada.idempotency_key,
            operation_type=declarada.operation_type,
            contract_version=1,
            local_sequence=99,
            clock=declarada.clock,
            payload=declarada.payload,
        )
        defeitos = dict(batch.inspect((fora,)))
        assert BatchStructuralDefect.SEQUENCIA_FORA_DA_FRONTEIRA in defeitos

    def test_digest_do_manifesto_e_reproduzivel(
        self, contexto: tuple[OrganizationId, UniversalReference, UniversalReference]
    ) -> None:
        org, device, actor = contexto
        batch = SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=(_operation(org, device, actor),),
            created_at_device=T0,
        )
        assert compute_manifest_digest(batch.manifest) == batch.manifest_digest


class TestSynchronizationResult:
    def _base(self, status: SynchronizationResultStatus, **overrides: object) -> object:
        argumentos: dict[str, object] = {
            "operation_id": TypedId.new("offline_operation"),
            "batch_id": TypedId.new("synchronization_batch"),
            "organization_id": OrganizationId.new(),
            "attempt": 1,
            "status": status,
            "decided_at": T0,
        }
        argumentos.update(overrides)
        return SynchronizationResult(**argumentos)  # type: ignore[arg-type]

    def test_aceita_exige_efeito_recuperavel(self) -> None:
        with pytest.raises(ValueError, match="efeito oficial produzido"):
            self._base(SynchronizationResultStatus.ACEITA)

    def test_rejeitada_nao_referencia_efeito(self) -> None:
        org = OrganizationId.new()
        with pytest.raises(ValueError, match="não produz efeito"):
            self._base(
                SynchronizationResultStatus.REJEITADA,
                organization_id=org,
                produced_references=(_ref(org, "fact"),),
            )

    def test_conflitante_exige_conflito_descrito(self) -> None:
        with pytest.raises(ValueError, match="CONFLITANTE exige conflito"):
            self._base(SynchronizationResultStatus.CONFLITANTE)

    def test_conflito_sem_status_conflitante_e_recusado(self) -> None:
        operation_id = TypedId.new("offline_operation")
        with pytest.raises(ValueError, match="CONFLITANTE exige conflito"):
            self._base(
                SynchronizationResultStatus.REJEITADA,
                operation_id=operation_id,
                conflict=SynchronizationConflict(
                    operation_id=operation_id,
                    reason=SynchronizationConflictReason.VERSAO_DIVERGENTE,
                    observed_state="estado divergente",
                    detected_at=T0,
                ),
            )

    def test_dependencia_pendente_exige_dependencias(self) -> None:
        with pytest.raises(ValueError, match="dependências que faltam"):
            self._base(SynchronizationResultStatus.DEPENDENCIA_PENDENTE)

    def test_resultado_desconhecido_exige_prazo_de_reconciliacao(self) -> None:
        with pytest.raises(ValueError, match="prazo de reconciliação"):
            self._base(SynchronizationResultStatus.RESULTADO_DESCONHECIDO)


class TestSynchronizationBatchResult:
    def _batch(self, quantidade: int) -> SynchronizationBatch:
        org = OrganizationId.new()
        device = _ref(org, "device")
        actor = _ref(org, "user")
        operacoes = tuple(
            _operation(org, device, actor, key=f"captura-000000{i}", sequence=i + 1)
            for i in range(quantidade)
        )
        return SynchronizationBatch.create(
            organization_id=org,
            device_reference=device,
            operations=operacoes,
            created_at_device=T0,
        )

    def _resultado(
        self,
        batch: SynchronizationBatch,
        posicao: int,
        status: SynchronizationResultStatus,
    ) -> SynchronizationResult:
        extras: dict[str, object] = {}
        if status is SynchronizationResultStatus.ACEITA:
            extras["produced_references"] = (_ref(batch.organization_id, "fact"),)
        if status is SynchronizationResultStatus.RESULTADO_DESCONHECIDO:
            extras["reconciliation_deadline"] = T0 + timedelta(hours=24)
        return SynchronizationResult(
            operation_id=batch.manifest[posicao].operation_id,
            batch_id=batch.batch_id,
            organization_id=batch.organization_id,
            attempt=1,
            status=status,
            decided_at=T0,
            **extras,  # type: ignore[arg-type]
        )

    def test_lote_inteiramente_aceito_fica_processado(self) -> None:
        batch = self._batch(2)
        resultado = SynchronizationBatchResult.from_results(
            batch=batch,
            results=tuple(
                self._resultado(batch, i, SynchronizationResultStatus.ACEITA) for i in range(2)
            ),
            attempt=1,
            processed_at=T0,
        )
        assert resultado.state is SynchronizationBatchState.PROCESSADO
        assert resultado.gaps == ()

    def test_lote_processado_nao_esconde_operacao_conflitante(self) -> None:
        batch = self._batch(2)
        resultado = SynchronizationBatchResult.from_results(
            batch=batch,
            results=(
                self._resultado(batch, 0, SynchronizationResultStatus.ACEITA),
                self._resultado(batch, 1, SynchronizationResultStatus.REJEITADA),
            ),
            attempt=1,
            processed_at=T0,
        )
        # O agregado nunca pode dizer "processado" quando há resultado não aceito.
        assert resultado.state is SynchronizationBatchState.PROCESSADO_PARCIALMENTE
        assert resultado.counts[SynchronizationResultStatus.REJEITADA] == 1

    def test_desconhecido_leva_a_reconciliacao(self) -> None:
        batch = self._batch(2)
        resultado = SynchronizationBatchResult.from_results(
            batch=batch,
            results=(
                self._resultado(batch, 0, SynchronizationResultStatus.ACEITA),
                self._resultado(batch, 1, SynchronizationResultStatus.RESULTADO_DESCONHECIDO),
            ),
            attempt=1,
            processed_at=T0,
        )
        assert resultado.state is SynchronizationBatchState.EM_RECONCILIACAO

    def test_lote_inteiramente_desconhecido_fica_indeterminado(self) -> None:
        batch = self._batch(1)
        resultado = SynchronizationBatchResult.from_results(
            batch=batch,
            results=(
                self._resultado(batch, 0, SynchronizationResultStatus.RESULTADO_DESCONHECIDO),
            ),
            attempt=1,
            processed_at=T0,
        )
        assert resultado.state is SynchronizationBatchState.RESULTADO_INDETERMINADO

    def test_operacao_nao_examinada_vira_lacuna(self) -> None:
        batch = self._batch(2)
        resultado = SynchronizationBatchResult.from_results(
            batch=batch,
            results=(self._resultado(batch, 0, SynchronizationResultStatus.ACEITA),),
            attempt=1,
            processed_at=T0,
        )
        assert resultado.state is SynchronizationBatchState.PROCESSADO_PARCIALMENTE
        assert resultado.gaps == (batch.manifest[1].operation_id,)

    def test_recusa_estrutural_nao_examina_nada(self) -> None:
        batch = self._batch(2)
        resultado = SynchronizationBatchResult.structurally_rejected(
            batch=batch,
            attempt=1,
            processed_at=T0,
            limitations=("DIGEST_DIVERGENTE: lote adulterado.",),
        )
        assert resultado.state is SynchronizationBatchState.REJEITADO_ESTRUTURALMENTE
        assert resultado.examined_count == 0
        assert len(resultado.gaps) == 2
