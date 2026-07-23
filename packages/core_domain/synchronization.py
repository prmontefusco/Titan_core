"""Contratos de operação offline e sincronização (ADR-0021 / Passo 7.9).

O Device captura intenção; somente o servidor produz efeito oficial. Este módulo
define o que o cliente envia e o que o servidor devolve, sem conhecer banco local,
sistema operacional, protocolo de transporte ou SDK de plataforma.
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import CanonicalSerializer, OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

_SERIALIZER = CanonicalSerializer()

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")
_CANONICAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_SEMANTIC_IDENTITY_PATTERN = re.compile(r"^[a-z][a-z0-9_.]*:[A-Za-z0-9._:\-]{1,200}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,99}$")


class TimeConfidenceLevel(StrEnum):
    """Confiança delimitada no horário alegado pelo Device.

    Nenhum nível transforma relógio de cliente em prova temporal: o mais alto
    apenas declara que houve contato recente com o servidor.
    """

    SINCRONIZADO_COM_SERVIDOR = "SINCRONIZADO_COM_SERVIDOR"
    MONOTONICO_LOCAL = "MONOTONICO_LOCAL"
    APENAS_RELOGIO_LOCAL = "APENAS_RELOGIO_LOCAL"
    INDETERMINADO = "INDETERMINADO"


class SynchronizationResultStatus(StrEnum):
    """Estados públicos do resultado individual de uma OfflineOperation."""

    ACEITA = "ACEITA"
    REJEITADA = "REJEITADA"
    DUPLICADA = "DUPLICADA"
    CONFLITANTE = "CONFLITANTE"
    DEPENDENCIA_PENDENTE = "DEPENDENCIA_PENDENTE"
    EM_QUARENTENA = "EM_QUARENTENA"
    RESULTADO_DESCONHECIDO = "RESULTADO_DESCONHECIDO"


class SynchronizationBatchState(StrEnum):
    """Estados públicos do resultado agregado de um SynchronizationBatch."""

    RECEBIDO = "RECEBIDO"
    VALIDADO_PARCIALMENTE = "VALIDADO_PARCIALMENTE"
    PROCESSADO_PARCIALMENTE = "PROCESSADO_PARCIALMENTE"
    PROCESSADO = "PROCESSADO"
    EM_RECONCILIACAO = "EM_RECONCILIACAO"
    REJEITADO_ESTRUTURALMENTE = "REJEITADO_ESTRUTURALMENTE"
    RESULTADO_INDETERMINADO = "RESULTADO_INDETERMINADO"


class SynchronizationConflictReason(StrEnum):
    """Motivos de conflito distinguíveis, nunca resolvidos silenciosamente."""

    IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE = "IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE"
    DEPENDENCIA_CICLICA = "DEPENDENCIA_CICLICA"
    DEPENDENCIA_INCOMPATIVEL = "DEPENDENCIA_INCOMPATIVEL"
    MANIFESTO_DIVERGENTE_ENTRE_RETOMADAS = "MANIFESTO_DIVERGENTE_ENTRE_RETOMADAS"
    RELOGIO_INSUFICIENTE = "RELOGIO_INSUFICIENTE"
    VERSAO_DIVERGENTE = "VERSAO_DIVERGENTE"
    AUTORIZACAO_ALTERADA = "AUTORIZACAO_ALTERADA"


class BatchStructuralDefect(StrEnum):
    """Divergências entre o manifesto declarado e as operações recebidas."""

    OPERACAO_AUSENTE = "OPERACAO_AUSENTE"
    OPERACAO_NAO_DECLARADA = "OPERACAO_NAO_DECLARADA"
    OPERACAO_DUPLICADA = "OPERACAO_DUPLICADA"
    DIGEST_DIVERGENTE = "DIGEST_DIVERGENTE"
    IDENTIDADE_SEMANTICA_DIVERGENTE = "IDENTIDADE_SEMANTICA_DIVERGENTE"
    ORGANIZATION_DIVERGENTE = "ORGANIZATION_DIVERGENTE"
    DEVICE_DIVERGENTE = "DEVICE_DIVERGENTE"
    SEQUENCIA_FORA_DA_FRONTEIRA = "SEQUENCIA_FORA_DA_FRONTEIRA"


@dataclass(frozen=True, slots=True)
class DeviceClockReading:
    """Leitura de relógio alegada pelo Device.

    Preserva horário observado, horário alegado do fato e a continuidade
    monotônica separadamente. A continuidade ordena apenas dentro dela mesma:
    não produz horário civil, ordem global nem precedência.
    """

    client_observed_at: datetime
    claimed_occurred_at: datetime
    timezone_name: str
    confidence: TimeConfidenceLevel
    monotonic_continuity_id: str = ""
    monotonic_elapsed_ms: int | None = None
    last_server_contact_at: datetime | None = None

    def __post_init__(self) -> None:
        require_utc(self.client_observed_at, field_name="client_observed_at")
        require_utc(self.claimed_occurred_at, field_name="claimed_occurred_at")
        if self.last_server_contact_at is not None:
            require_utc(self.last_server_contact_at, field_name="last_server_contact_at")
        if not isinstance(self.timezone_name, str) or not self.timezone_name.strip():
            raise ValueError("timezone_name deve ser declarado pelo Device.")
        if not isinstance(self.confidence, TimeConfidenceLevel):
            raise TypeError("confidence deve ser um TimeConfidenceLevel.")
        if self.monotonic_elapsed_ms is not None:
            if not isinstance(self.monotonic_elapsed_ms, int) or self.monotonic_elapsed_ms < 0:
                raise ValueError("monotonic_elapsed_ms deve ser inteiro não negativo.")
            if not self.monotonic_continuity_id.strip():
                raise ValueError(
                    "Medida monotônica sem continuidade declarada não ordena nada: "
                    "informe monotonic_continuity_id."
                )
        if (
            self.confidence is TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR
            and self.last_server_contact_at is None
        ):
            raise ValueError("SINCRONIZADO_COM_SERVIDOR exige o último contato com o servidor.")
        if (
            self.confidence is TimeConfidenceLevel.MONOTONICO_LOCAL
            and not self.monotonic_continuity_id.strip()
        ):
            raise ValueError("MONOTONICO_LOCAL exige continuidade monotônica declarada.")

    def precedes(self, other: "DeviceClockReading") -> bool | None:
        """Ordem relativa entre duas leituras, quando ela existir.

        Só há resposta dentro da mesma continuidade monotônica. Fora dela o
        retorno é `None`: continuidade perdida ou relógio civil não sustentam
        precedência, e afirmar ordem nesse caso seria inventar prova.
        """
        if (
            not self.monotonic_continuity_id.strip()
            or self.monotonic_continuity_id != other.monotonic_continuity_id
            or self.monotonic_elapsed_ms is None
            or other.monotonic_elapsed_ms is None
        ):
            return None
        return self.monotonic_elapsed_ms < other.monotonic_elapsed_ms


def compute_intent_digest(
    *,
    organization_id: OrganizationId,
    semantic_identity: str,
    operation_type: str,
    contract_version: int,
    payload: CanonicalPayload,
) -> str:
    """Digest da intenção, e não do envelope.

    Deliberadamente ignora OperationId, sequência local, relógio e tentativa: são
    esses campos que mudam entre retomadas do mesmo comando. Incluí-los faria a
    mesma intenção parecer diferente a cada reenvio e destruiria a idempotência.
    """
    return hashlib.sha256(
        _SERIALIZER.serialize(
            {
                "contract_version": contract_version,
                "organization_id": str(organization_id.value),
                "operation_type": operation_type,
                "payload_schema": payload.schema,
                "payload_version": payload.version,
                "payload_digest": hashlib.sha256(payload.canonical_bytes).hexdigest(),
                "semantic_identity": semantic_identity,
            }
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class OfflineOperation:
    """Envelope append-only de uma intenção capturada sem conexão.

    Editar uma operação enviada cria outra operação correlacionada; este envelope
    nunca é reescrito. Segredo, token e credencial não integram o conteúdo — a
    proibição é herdada de `CanonicalPayload`.
    """

    operation_id: TypedId
    organization_id: OrganizationId
    device_reference: UniversalReference
    actor_reference: UniversalReference
    semantic_identity: str
    idempotency_key: str
    operation_type: str
    contract_version: int
    local_sequence: int
    clock: DeviceClockReading
    payload: CanonicalPayload
    depends_on: tuple[TypedId, ...] = field(default_factory=tuple)
    evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    correlation_id: TypedId | None = None

    def __post_init__(self) -> None:
        if self.operation_id.entity_type != "offline_operation":
            raise ValueError("operation_id deve ser do tipo 'offline_operation'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if self.device_reference.target_id.entity_type != "device":
            raise ValueError("device_reference deve apontar para um 'device'.")
        for label, reference in (
            ("device_reference", self.device_reference),
            ("actor_reference", self.actor_reference),
        ):
            if not isinstance(reference, UniversalReference):
                raise TypeError(f"{label} deve ser UniversalReference.")
            if reference.organization_id != self.organization_id:
                raise ValueError(f"{label} deve pertencer à Organization da operação.")
        if not _SEMANTIC_IDENTITY_PATTERN.fullmatch(self.semantic_identity):
            raise ValueError(
                "semantic_identity deve usar 'tipo.canonico:discriminador' — é ela que "
                "define quando duas capturas são a mesma intenção."
            )
        if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(self.idempotency_key):
            raise ValueError("idempotency_key possui formato inválido.")
        if not _CANONICAL_NAME_PATTERN.fullmatch(self.operation_type):
            raise ValueError("operation_type deve usar nome canônico em minúsculas.")
        if not isinstance(self.contract_version, int) or self.contract_version < 1:
            raise ValueError("contract_version deve ser inteiro >= 1.")
        if not isinstance(self.local_sequence, int) or self.local_sequence < 1:
            raise ValueError("local_sequence deve ser inteiro >= 1.")
        if not isinstance(self.clock, DeviceClockReading):
            raise TypeError("clock deve ser DeviceClockReading.")
        if not isinstance(self.payload, CanonicalPayload):
            raise TypeError("payload deve ser CanonicalPayload.")
        if not isinstance(self.depends_on, tuple):
            raise TypeError("depends_on deve ser uma tupla.")
        for dependency in self.depends_on:
            if dependency.entity_type != "offline_operation":
                raise ValueError("Dependência deve referenciar uma 'offline_operation'.")
            if dependency == self.operation_id:
                raise ValueError("Uma operação não pode depender de si mesma.")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("depends_on não pode repetir a mesma dependência.")
        if not isinstance(self.evidence_references, tuple):
            raise TypeError("evidence_references deve ser uma tupla.")

    @property
    def intent_digest(self) -> str:
        return compute_intent_digest(
            organization_id=self.organization_id,
            semantic_identity=self.semantic_identity,
            operation_type=self.operation_type,
            contract_version=self.contract_version,
            payload=self.payload,
        )


@dataclass(frozen=True, slots=True)
class OperationManifestEntry:
    """Entrada do manifesto: o que o Device declara ter enviado."""

    operation_id: TypedId
    semantic_identity: str
    intent_digest: str
    position: int
    depends_on: tuple[TypedId, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.operation_id.entity_type != "offline_operation":
            raise ValueError("operation_id do manifesto deve ser 'offline_operation'.")
        if not _SEMANTIC_IDENTITY_PATTERN.fullmatch(self.semantic_identity):
            raise ValueError("semantic_identity do manifesto é inválida.")
        if not isinstance(self.intent_digest, str) or len(self.intent_digest) != 64:
            raise ValueError("intent_digest deve ser um SHA-256 em hexadecimal.")
        if not isinstance(self.position, int) or self.position < 0:
            raise ValueError("position deve ser inteiro não negativo.")

    def to_canonical(self) -> dict[str, Any]:
        return {
            "depends_on": [str(d.value) for d in self.depends_on],
            "intent_digest": self.intent_digest,
            "operation_id": str(self.operation_id.value),
            "position": self.position,
            "semantic_identity": self.semantic_identity,
        }


def compute_manifest_digest(entries: tuple[OperationManifestEntry, ...]) -> str:
    """Digest do manifesto inteiro, na ordem física declarada.

    Detecta remoção, duplicação, substituição e alteração de operação entre
    retomadas. Não substitui os digests individuais e não transforma a posição
    física em causalidade.
    """
    return hashlib.sha256(
        _SERIALIZER.serialize({"entries": [entry.to_canonical() for entry in entries]})
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SynchronizationBatch:
    """Conjunto delimitado de operações enviado ao servidor.

    O lote não é unidade atômica de negócio: transporta e comprova cobertura,
    mas cada operação recebe resultado individual.
    """

    batch_id: TypedId
    batch_version: int
    organization_id: OrganizationId
    device_reference: UniversalReference
    manifest: tuple[OperationManifestEntry, ...]
    operation_count: int
    manifest_digest: str
    sequence_boundary: tuple[int, int]
    created_at_device: datetime

    def __post_init__(self) -> None:
        if self.batch_id.entity_type != "synchronization_batch":
            raise ValueError("batch_id deve ser do tipo 'synchronization_batch'.")
        if not isinstance(self.batch_version, int) or self.batch_version < 1:
            raise ValueError("batch_version deve ser inteiro >= 1.")
        if self.device_reference.target_id.entity_type != "device":
            raise ValueError("device_reference deve apontar para um 'device'.")
        if self.device_reference.organization_id != self.organization_id:
            raise ValueError("device_reference deve pertencer à Organization do lote.")
        if not isinstance(self.manifest, tuple) or not self.manifest:
            raise ValueError("O lote exige manifesto com ao menos uma entrada.")
        if self.operation_count != len(self.manifest):
            raise ValueError("operation_count deve coincidir com o tamanho do manifesto.")
        positions = [entry.position for entry in self.manifest]
        if sorted(positions) != list(range(len(self.manifest))):
            raise ValueError("As posições do manifesto devem ser 0..n-1 sem repetição.")
        identifiers = [entry.operation_id for entry in self.manifest]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("O manifesto não pode declarar a mesma operação duas vezes.")
        if compute_manifest_digest(self.manifest) != self.manifest_digest:
            raise ValueError("manifest_digest não confere com o manifesto declarado.")
        first, last = self.sequence_boundary
        if not isinstance(first, int) or not isinstance(last, int) or first < 1 or last < first:
            raise ValueError("sequence_boundary deve ser um intervalo local válido.")
        require_utc(self.created_at_device, field_name="created_at_device")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        device_reference: UniversalReference,
        operations: tuple[OfflineOperation, ...],
        created_at_device: datetime,
        batch_version: int = 1,
        batch_id: TypedId | None = None,
    ) -> "SynchronizationBatch":
        """Monta o lote a partir das operações, na ordem física recebida."""
        if not operations:
            raise ValueError("Um lote exige ao menos uma operação.")
        manifest = tuple(
            OperationManifestEntry(
                operation_id=operation.operation_id,
                semantic_identity=operation.semantic_identity,
                intent_digest=operation.intent_digest,
                position=position,
                depends_on=operation.depends_on,
            )
            for position, operation in enumerate(operations)
        )
        sequences = [operation.local_sequence for operation in operations]
        return cls(
            batch_id=batch_id or TypedId.new("synchronization_batch"),
            batch_version=batch_version,
            organization_id=organization_id,
            device_reference=device_reference,
            manifest=manifest,
            operation_count=len(manifest),
            manifest_digest=compute_manifest_digest(manifest),
            sequence_boundary=(min(sequences), max(sequences)),
            created_at_device=created_at_device,
        )

    def inspect(
        self, operations: tuple[OfflineOperation, ...]
    ) -> tuple[tuple[BatchStructuralDefect, str], ...]:
        """Confronta o manifesto com as operações efetivamente recebidas.

        Devolve todos os defeitos encontrados em vez de parar no primeiro: o
        cliente precisa corrigir o lote inteiro, não descobrir um problema por
        retomada.
        """
        defects: list[tuple[BatchStructuralDefect, str]] = []
        received: dict[TypedId, OfflineOperation] = {}
        for operation in operations:
            if operation.operation_id in received:
                defects.append(
                    (
                        BatchStructuralDefect.OPERACAO_DUPLICADA,
                        f"Operação {operation.operation_id.value} recebida mais de uma vez.",
                    )
                )
                continue
            received[operation.operation_id] = operation

        declared = {entry.operation_id: entry for entry in self.manifest}
        first, last = self.sequence_boundary

        for operation_id in declared.keys() - received.keys():
            defects.append(
                (
                    BatchStructuralDefect.OPERACAO_AUSENTE,
                    f"Operação {operation_id.value} declarada e não recebida.",
                )
            )
        for operation_id in received.keys() - declared.keys():
            defects.append(
                (
                    BatchStructuralDefect.OPERACAO_NAO_DECLARADA,
                    f"Operação {operation_id.value} recebida e não declarada.",
                )
            )

        for operation_id, entry in declared.items():
            declared_operation = received.get(operation_id)
            if declared_operation is None:
                continue
            if declared_operation.intent_digest != entry.intent_digest:
                defects.append(
                    (
                        BatchStructuralDefect.DIGEST_DIVERGENTE,
                        f"Operação {operation_id.value} não confere com o digest declarado.",
                    )
                )
            if declared_operation.semantic_identity != entry.semantic_identity:
                defects.append(
                    (
                        BatchStructuralDefect.IDENTIDADE_SEMANTICA_DIVERGENTE,
                        f"Operação {operation_id.value} mudou de identidade semântica.",
                    )
                )
            if declared_operation.organization_id != self.organization_id:
                defects.append(
                    (
                        BatchStructuralDefect.ORGANIZATION_DIVERGENTE,
                        f"Operação {operation_id.value} pertence a outra Organization.",
                    )
                )
            if declared_operation.device_reference != self.device_reference:
                defects.append(
                    (
                        BatchStructuralDefect.DEVICE_DIVERGENTE,
                        f"Operação {operation_id.value} veio de outro Device.",
                    )
                )
            if not first <= declared_operation.local_sequence <= last:
                defects.append(
                    (
                        BatchStructuralDefect.SEQUENCIA_FORA_DA_FRONTEIRA,
                        f"Operação {operation_id.value} está fora da fronteira de sequência.",
                    )
                )
        return tuple(defects)


@dataclass(frozen=True, slots=True)
class SynchronizationConflict:
    """Conflito explícito, preservado para resolução autorizada.

    Não carrega resolução automática: last-write-wins, maior timestamp do Device
    e último lote recebido são justamente o que esta estrutura existe para evitar.
    """

    operation_id: TypedId
    reason: SynchronizationConflictReason
    observed_state: str
    detected_at: datetime
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    responsible_actor_reference: UniversalReference | None = None

    def __post_init__(self) -> None:
        if self.operation_id.entity_type != "offline_operation":
            raise ValueError("operation_id do conflito deve ser 'offline_operation'.")
        if not isinstance(self.reason, SynchronizationConflictReason):
            raise TypeError("reason deve ser SynchronizationConflictReason.")
        if not isinstance(self.observed_state, str) or not self.observed_state.strip():
            raise ValueError("observed_state deve descrever o estado observado.")
        require_utc(self.detected_at, field_name="detected_at")
        if not isinstance(self.alternatives, tuple):
            raise TypeError("alternatives deve ser uma tupla.")


@dataclass(frozen=True, slots=True)
class SynchronizationResult:
    """Resultado individual e recuperável de uma OfflineOperation."""

    operation_id: TypedId
    batch_id: TypedId
    organization_id: OrganizationId
    attempt: int
    status: SynchronizationResultStatus
    decided_at: datetime
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    produced_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    conflict: SynchronizationConflict | None = None
    pending_dependencies: tuple[TypedId, ...] = field(default_factory=tuple)
    reconciliation_deadline: datetime | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.operation_id.entity_type != "offline_operation":
            raise ValueError("operation_id do resultado deve ser 'offline_operation'.")
        if self.batch_id.entity_type != "synchronization_batch":
            raise ValueError("batch_id do resultado deve ser 'synchronization_batch'.")
        if not isinstance(self.status, SynchronizationResultStatus):
            raise TypeError("status deve ser SynchronizationResultStatus.")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt deve ser inteiro >= 1.")
        require_utc(self.decided_at, field_name="decided_at")
        if self.reconciliation_deadline is not None:
            require_utc(self.reconciliation_deadline, field_name="reconciliation_deadline")
        for code in self.reason_codes:
            if not _REASON_CODE_PATTERN.fullmatch(code):
                raise ValueError(f"ReasonCode inválido: {code!r}.")

        # `ACEITA` afirma que existe efeito oficial; sem referência ao objeto
        # produzido, a afirmação não seria recuperável nem auditável.
        if self.status is SynchronizationResultStatus.ACEITA and not self.produced_references:
            raise ValueError("ACEITA exige ao menos uma referência ao efeito oficial produzido.")
        if self.status is not SynchronizationResultStatus.ACEITA and self.produced_references:
            if self.status is not SynchronizationResultStatus.DUPLICADA:
                raise ValueError(
                    "Somente ACEITA e DUPLICADA referenciam efeito oficial: "
                    f"{self.status.value} não produz efeito."
                )
        if (self.conflict is not None) != (self.status is SynchronizationResultStatus.CONFLITANTE):
            raise ValueError("CONFLITANTE exige conflito descrito, e só ele o admite.")
        if self.conflict is not None and self.conflict.operation_id != self.operation_id:
            raise ValueError("O conflito deve descrever a própria operação.")
        if (
            self.status is SynchronizationResultStatus.DEPENDENCIA_PENDENTE
            and not self.pending_dependencies
        ):
            raise ValueError("DEPENDENCIA_PENDENTE exige as dependências que faltam.")
        # `RESULTADO_DESCONHECIDO` descreve o conhecimento de um participante em um
        # instante. Sem prazo de reconciliação ele viraria pendência permanente,
        # que é exatamente o que a ADR-0021 proíbe.
        if (
            self.status is SynchronizationResultStatus.RESULTADO_DESCONHECIDO
            and self.reconciliation_deadline is None
        ):
            raise ValueError("RESULTADO_DESCONHECIDO exige prazo de reconciliação.")


@dataclass(frozen=True, slots=True)
class SynchronizationBatchResult:
    """Resultado agregado e reconstruível do lote.

    Conta e resume; nunca substitui nem reduz a precisão dos resultados
    individuais, que permanecem recuperáveis por OperationId.
    """

    batch_id: TypedId
    organization_id: OrganizationId
    state: SynchronizationBatchState
    manifest_digest: str
    attempt: int
    expected_count: int
    examined_count: int
    counts: Mapping[SynchronizationResultStatus, int]
    processed_at: datetime
    gaps: tuple[TypedId, ...] = field(default_factory=tuple)
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.batch_id.entity_type != "synchronization_batch":
            raise ValueError("batch_id deve ser do tipo 'synchronization_batch'.")
        if not isinstance(self.state, SynchronizationBatchState):
            raise TypeError("state deve ser SynchronizationBatchState.")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt deve ser inteiro >= 1.")
        if self.examined_count != sum(self.counts.values()):
            raise ValueError("examined_count deve coincidir com a soma das contagens.")
        if self.examined_count > self.expected_count:
            raise ValueError("Não é possível examinar mais operações do que o esperado.")
        require_utc(self.processed_at, field_name="processed_at")

    @classmethod
    def from_results(
        cls,
        *,
        batch: SynchronizationBatch,
        results: tuple[SynchronizationResult, ...],
        attempt: int,
        processed_at: datetime,
        limitations: tuple[str, ...] = (),
    ) -> "SynchronizationBatchResult":
        counts: dict[SynchronizationResultStatus, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        examined = {result.operation_id for result in results}
        gaps = tuple(
            entry.operation_id for entry in batch.manifest if entry.operation_id not in examined
        )
        return cls(
            batch_id=batch.batch_id,
            organization_id=batch.organization_id,
            state=_derive_batch_state(counts=counts, gaps=gaps),
            manifest_digest=batch.manifest_digest,
            attempt=attempt,
            expected_count=batch.operation_count,
            examined_count=len(results),
            counts=dict(counts),
            processed_at=processed_at,
            gaps=gaps,
            limitations=limitations,
        )

    @classmethod
    def structurally_rejected(
        cls,
        *,
        batch: SynchronizationBatch,
        attempt: int,
        processed_at: datetime,
        limitations: tuple[str, ...],
    ) -> "SynchronizationBatchResult":
        """Lote recusado antes de qualquer efeito: nenhuma operação foi examinada."""
        return cls(
            batch_id=batch.batch_id,
            organization_id=batch.organization_id,
            state=SynchronizationBatchState.REJEITADO_ESTRUTURALMENTE,
            manifest_digest=batch.manifest_digest,
            attempt=attempt,
            expected_count=batch.operation_count,
            examined_count=0,
            counts={},
            processed_at=processed_at,
            gaps=tuple(entry.operation_id for entry in batch.manifest),
            limitations=limitations,
        )


def _derive_batch_state(
    *,
    counts: Mapping[SynchronizationResultStatus, int],
    gaps: tuple[TypedId, ...],
) -> SynchronizationBatchState:
    """Deriva o estado agregado sem esconder nenhum resultado individual.

    A ordem das perguntas é deliberada: desconhecido vence tudo, porque um efeito
    possivelmente aplicado e não confirmado é a situação mais grave; só depois
    vêm lacunas, resultados não aceitos e, por último, a aceitação integral.
    """
    unknown = counts.get(SynchronizationResultStatus.RESULTADO_DESCONHECIDO, 0)
    if unknown and unknown == sum(counts.values()) and not gaps:
        return SynchronizationBatchState.RESULTADO_INDETERMINADO
    if unknown:
        return SynchronizationBatchState.EM_RECONCILIACAO
    if gaps:
        return SynchronizationBatchState.PROCESSADO_PARCIALMENTE
    accepted = counts.get(SynchronizationResultStatus.ACEITA, 0)
    duplicated = counts.get(SynchronizationResultStatus.DUPLICADA, 0)
    total = sum(counts.values())
    if accepted + duplicated == total:
        return SynchronizationBatchState.PROCESSADO
    return SynchronizationBatchState.PROCESSADO_PARCIALMENTE


# -- Deep Offline Capability & Admissão de Dispositivos (ADR-0021 / Passo 7.9) ---


@dataclass(frozen=True, slots=True)
class OfflineCapabilityProfile:
    """Perfil de capacidades offline autorizadas para um dispositivo."""

    profile_id: TypedId
    device_id: TypedId
    allowed_operations: tuple[str, ...]
    max_offline_hours: int = 72
    requires_biometric_auth: bool = False

    def __post_init__(self) -> None:
        if self.profile_id.entity_type != "capability_profile":
            raise ValueError("profile_id deve ser do tipo 'capability_profile'.")
        if self.device_id.entity_type != "device":
            raise ValueError("device_id deve ser do tipo 'device'.")
        if not isinstance(self.allowed_operations, tuple):
            raise TypeError("allowed_operations deve ser uma tupla de strings.")
        if self.max_offline_hours < 1:
            raise ValueError("max_offline_hours deve ser >= 1.")

    def is_operation_allowed(self, operation_type: str) -> bool:
        return operation_type.strip().lower() in {
            op.strip().lower() for op in self.allowed_operations
        }


@dataclass(frozen=True, slots=True)
class OfflineSession:
    """Sessão offline emitida pelo servidor e mantida em cache assinado pelo dispositivo."""

    session_id: TypedId
    device_id: TypedId
    organization_id: OrganizationId
    issued_at: datetime
    expires_at: datetime
    session_token_hash: str
    capability_profile: OfflineCapabilityProfile

    def __post_init__(self) -> None:
        if self.session_id.entity_type != "offline_session":
            raise ValueError("session_id deve ser do tipo 'offline_session'.")
        if self.device_id.entity_type != "device":
            raise ValueError("device_id deve ser do tipo 'device'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.session_token_hash, str) or not self.session_token_hash.strip():
            raise ValueError("session_token_hash deve ser uma string não vazia.")

        require_utc(self.issued_at, field_name="issued_at")
        require_utc(self.expires_at, field_name="expires_at")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at deve ser posterior a issued_at.")

    def is_valid_at(self, current_time: datetime) -> bool:
        require_utc(current_time, field_name="current_time")
        return self.issued_at <= current_time < self.expires_at


@dataclass(frozen=True, slots=True)
class OfflineAuthorizationSnapshot:
    """Snapshot assinado das permissões de um usuário para operação offline."""

    snapshot_id: TypedId
    session_id: TypedId
    principal_id: TypedId
    granted_permissions: tuple[str, ...]
    as_of: datetime
    snapshot_signature: str

    def __post_init__(self) -> None:
        if self.snapshot_id.entity_type != "authorization_snapshot":
            raise ValueError("snapshot_id deve ser do tipo 'authorization_snapshot'.")
        if self.session_id.entity_type != "offline_session":
            raise ValueError("session_id deve ser do tipo 'offline_session'.")
        if not isinstance(self.granted_permissions, tuple):
            raise TypeError("granted_permissions deve ser uma tupla.")
        if not isinstance(self.snapshot_signature, str) or not self.snapshot_signature.strip():
            raise ValueError("snapshot_signature deve ser não vazia.")

        require_utc(self.as_of, field_name="as_of")

    def has_permission(self, permission: str) -> bool:
        return permission.strip() in self.granted_permissions


@dataclass(frozen=True, slots=True)
class DeviceTrustAssessment:
    """Avaliação de integridade e postura de segurança de um dispositivo offline."""

    device_id: TypedId
    trust_score: float
    os_version: str
    is_jailbroken_or_rooted: bool
    hardware_backed_keystore: bool
    assessed_at: datetime

    def __post_init__(self) -> None:
        if self.device_id.entity_type != "device":
            raise ValueError("device_id deve ser do tipo 'device'.")
        if not (0.0 <= self.trust_score <= 1.0):
            raise ValueError("trust_score deve estar no intervalo [0.0, 1.0].")
        if not isinstance(self.os_version, str) or not self.os_version.strip():
            raise ValueError("os_version deve ser uma string não vazia.")

        require_utc(self.assessed_at, field_name="assessed_at")

    def meets_trust_threshold(self, min_threshold: float = 0.7) -> bool:
        if self.is_jailbroken_or_rooted:
            return False
        return self.trust_score >= min_threshold


@dataclass(frozen=True, slots=True)
class LocalPreview:
    """Simulação in-memory de efeito local no cliente para operação offline."""

    intent_digest: str
    predicted_outcome: str
    predicted_state_changes: dict[str, Any]
    preview_generated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.intent_digest, str) or not self.intent_digest.strip():
            raise ValueError("intent_digest deve ser não vazio.")
        if self.predicted_outcome not in {"ACEITA", "CONFLITO_PROVAVEL", "REJEICAO_PROVAVEL"}:
            raise ValueError("predicted_outcome inválido.")
        if not isinstance(self.predicted_state_changes, dict):
            raise TypeError("predicted_state_changes deve ser dicionário.")

        require_utc(self.preview_generated_at, field_name="preview_generated_at")
