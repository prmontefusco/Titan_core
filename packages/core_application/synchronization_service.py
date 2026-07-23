"""Recepção e revalidação de lotes de operações offline (ADR-0021 / Passo 7.9).

O servidor decide o efeito oficial. A captura chega como alegação: identidade,
Device, relógio, dependências e idempotência são revalidados aqui, e o contexto
alegado nunca é reescrito pelo conhecimento posterior.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from packages.core_domain.synchronization import (
    OfflineOperation,
    SynchronizationBatch,
    SynchronizationBatchResult,
    SynchronizationConflict,
    SynchronizationConflictReason,
    SynchronizationResult,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import require_utc

# Prazo padrão para reconciliar um efeito possivelmente aplicado e não confirmado.
# Existe porque `RESULTADO_DESCONHECIDO` sem prazo vira pendência permanente.
DEFAULT_RECONCILIATION_WINDOW = timedelta(hours=24)

# Estados que ainda não decidiram nada e não aplicaram efeito: o reenvio deve
# reavaliá-los, senão a dependência aceita depois nunca destravaria a operação e
# o Device revogado por engano ficaria em quarentena para sempre. Os demais
# estados são recuperados, inclusive `RESULTADO_DESCONHECIDO`: reprocessá-lo
# poderia repetir um efeito que talvez já exista.
_REEVALUATED_ON_RETRY = frozenset(
    {
        SynchronizationResultStatus.DEPENDENCIA_PENDENTE,
        SynchronizationResultStatus.EM_QUARENTENA,
    }
)


class DeviceAdmission(StrEnum):
    """Admissão do Device para produzir efeito nesta sincronização."""

    PERMITIDO = "PERMITIDO"
    EM_QUARENTENA = "EM_QUARENTENA"
    BLOQUEADO = "BLOQUEADO"


class OfficialEffectRejected(RuntimeError):
    """O servidor recusou o efeito oficial; a captura permanece preservada."""

    def __init__(self, *reason_codes: str) -> None:
        super().__init__(", ".join(reason_codes) or "OPERACAO_REJEITADA")
        self.reason_codes = reason_codes or ("OPERACAO_REJEITADA",)


class OfficialEffectConflict(RuntimeError):
    """Estado atual incompatível com a captura; exige resolução autorizada."""

    def __init__(
        self,
        reason: SynchronizationConflictReason,
        observed_state: str,
        alternatives: tuple[str, ...] = (),
    ) -> None:
        super().__init__(f"{reason.value}: {observed_state}")
        self.reason = reason
        self.observed_state = observed_state
        self.alternatives = alternatives


class OfficialEffectResultUnknown(RuntimeError):
    """O efeito pode ter sido aplicado; o resultado não é conhecido."""

    def __init__(self, observed_state: str) -> None:
        super().__init__(observed_state)
        self.observed_state = observed_state


class SynchronizationRepositoryPort(Protocol):
    def get_batch_manifest_digest(self, batch_id: TypedId) -> str | None: ...

    def register_batch(self, batch: SynchronizationBatch, received_at: datetime) -> int:
        """Registra a chegada do lote e devolve o número da tentativa."""
        ...

    def save_operation(self, operation: OfflineOperation) -> None: ...

    def save_result(self, result: SynchronizationResult) -> None: ...

    def save_batch_result(self, batch_result: SynchronizationBatchResult) -> None: ...

    def get_result(self, operation_id: TypedId) -> SynchronizationResult | None: ...

    def find_by_idempotency_key(
        self, organization_id: OrganizationId, idempotency_key: str
    ) -> tuple[TypedId, str] | None:
        """Devolve `(operation_id, intent_digest)` da primeira captura com a chave."""
        ...


class DeviceAdmissionPort(Protocol):
    def admit(
        self,
        organization_id: OrganizationId,
        device_reference: UniversalReference,
        at: datetime,
    ) -> DeviceAdmission: ...


class AlwaysAdmitsDevice:
    """Admissão permissiva para ambientes sem inventário de Devices.

    Existe para que a porta seja explícita mesmo antes do DeviceTrustAssessment:
    quem não avalia Device declara isso, em vez de não ter onde avaliar.
    """

    def admit(
        self,
        organization_id: OrganizationId,
        device_reference: UniversalReference,
        at: datetime,
    ) -> DeviceAdmission:
        return DeviceAdmission.PERMITIDO


# O handler aplica o efeito oficial e devolve as referências produzidas.
OfficialEffectHandler = Callable[[OfflineOperation], tuple[UniversalReference, ...]]


@dataclass(frozen=True, slots=True)
class SynchronizationService:
    """Recebe lotes, revalida cada operação e produz resultados individuais.

    A ordem física do lote não é causalidade: o processamento segue as
    dependências declaradas. Conflito nunca é resolvido silenciosamente, e o
    resultado agregado nunca substitui os resultados individuais.
    """

    repository: SynchronizationRepositoryPort
    effect_handler: OfficialEffectHandler
    device_admission: DeviceAdmissionPort = AlwaysAdmitsDevice()
    reconciliation_window: timedelta = DEFAULT_RECONCILIATION_WINDOW

    def receive_batch(
        self,
        batch: SynchronizationBatch,
        operations: tuple[OfflineOperation, ...],
        received_at: datetime,
    ) -> SynchronizationBatchResult:
        require_utc(received_at, field_name="received_at")

        structural = self._structural_limitations(batch, operations)
        if structural:
            attempt = self.repository.register_batch(batch, received_at)
            batch_result = SynchronizationBatchResult.structurally_rejected(
                batch=batch,
                attempt=attempt,
                processed_at=received_at,
                limitations=structural,
            )
            self.repository.save_batch_result(batch_result)
            return batch_result

        batch_attempt = self.repository.register_batch(batch, received_at)
        by_id = {operation.operation_id: operation for operation in operations}
        results: list[SynchronizationResult] = []
        decided: dict[TypedId, SynchronizationResultStatus] = {}

        for operation in self._dependency_order(operations):
            # A tentativa é da operação, não do lote: a mesma captura pode ser
            # reenviada em lotes diferentes, e o histórico append-only por
            # tentativa perderia a decisão nova se ela recomeçasse do um.
            stored = self.repository.get_result(operation.operation_id)
            result = self._process(
                operation=operation,
                batch=batch,
                attempt=1 if stored is None else stored.attempt + 1,
                received_at=received_at,
                decided=decided,
                in_batch=by_id,
                stored=stored,
            )
            self.repository.save_operation(operation)
            self.repository.save_result(result)
            decided[operation.operation_id] = result.status
            results.append(result)

        batch_result = SynchronizationBatchResult.from_results(
            batch=batch,
            results=tuple(results),
            attempt=batch_attempt,
            processed_at=received_at,
        )
        self.repository.save_batch_result(batch_result)
        return batch_result

    def _structural_limitations(
        self, batch: SynchronizationBatch, operations: tuple[OfflineOperation, ...]
    ) -> tuple[str, ...]:
        """Defeitos que impedem examinar o lote, incluindo troca de manifesto.

        Manifesto alterado entre retomadas é recusa estrutural, e não conflito por
        operação: aceitar o lote novo permitiria substituir capturas já enviadas
        preservando o mesmo BatchId.
        """
        limitations = [f"{defect.value}: {detail}" for defect, detail in batch.inspect(operations)]
        known_digest = self.repository.get_batch_manifest_digest(batch.batch_id)
        if known_digest is not None and known_digest != batch.manifest_digest:
            limitations.append(
                f"{SynchronizationConflictReason.MANIFESTO_DIVERGENTE_ENTRE_RETOMADAS.value}: "
                f"o lote {batch.batch_id.value} já foi recebido com outro manifesto."
            )
        return tuple(limitations)

    @staticmethod
    def _dependency_order(
        operations: tuple[OfflineOperation, ...],
    ) -> list[OfflineOperation]:
        """Ordena por dependência declarada, preservando a ordem física no empate.

        Operações em ciclo permanecem no final e são decididas como conflito: um
        ciclo não pode ficar pendente indefinidamente esperando a si mesmo.
        """
        pending = {operation.operation_id: operation for operation in operations}
        ordered: list[OfflineOperation] = []
        placed: set[TypedId] = set()

        while pending:
            ready = [
                operation
                for operation in pending.values()
                if all(
                    dependency not in pending or dependency in placed
                    for dependency in operation.depends_on
                )
            ]
            if not ready:
                # Só sobraram operações que dependem umas das outras.
                ordered.extend(pending.values())
                break
            for operation in ready:
                ordered.append(operation)
                placed.add(operation.operation_id)
                del pending[operation.operation_id]
        return ordered

    def _process(
        self,
        *,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
        decided: dict[TypedId, SynchronizationResultStatus],
        in_batch: dict[TypedId, OfflineOperation],
        stored: SynchronizationResult | None,
    ) -> SynchronizationResult:
        recovered = self._recovered_result(operation, batch, attempt, received_at, stored)
        if recovered is not None:
            return recovered

        conflict = self._idempotency_conflict(operation, batch, attempt, received_at)
        if conflict is not None:
            return conflict

        clock_conflict = self._clock_conflict(operation, batch, attempt, received_at)
        if clock_conflict is not None:
            return clock_conflict

        dependency = self._dependency_result(
            operation, batch, attempt, received_at, decided, in_batch
        )
        if dependency is not None:
            return dependency

        admission = self.device_admission.admit(
            operation.organization_id, operation.device_reference, received_at
        )
        if admission is not DeviceAdmission.PERMITIDO:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=SynchronizationResultStatus.EM_QUARENTENA,
                decided_at=received_at,
                reason_codes=(f"DEVICE_{admission.value}",),
                limitations=(
                    "A captura permanece preservada; o Device não está admitido a "
                    "produzir efeito oficial neste instante.",
                ),
            )

        return self._apply_effect(operation, batch, attempt, received_at)

    def _recovered_result(
        self,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
        stored: SynchronizationResult | None,
    ) -> SynchronizationResult | None:
        """Recupera resultado já decidido, em vez de repetir o efeito.

        Distingue os dois reenvios possíveis. A mesma operação recupera o próprio
        resultado com o estado preservado — inclusive rejeição e desconhecido, que
        um reenvio não converte em sucesso. Uma captura diferente da mesma intenção
        sob a mesma IdempotencyKey é `DUPLICADA`, porque é outro envelope.
        """
        if stored is not None and stored.status not in _REEVALUATED_ON_RETRY:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=stored.status,
                decided_at=received_at,
                reason_codes=tuple(dict.fromkeys(("RESULTADO_RECUPERADO", *stored.reason_codes))),
                produced_references=stored.produced_references,
                conflict=stored.conflict,
                pending_dependencies=stored.pending_dependencies,
                reconciliation_deadline=stored.reconciliation_deadline,
                limitations=stored.limitations,
            )

        existing = self.repository.find_by_idempotency_key(
            operation.organization_id, operation.idempotency_key
        )
        # `existing` pode ser a própria operação já gravada numa tentativa
        # anterior. Nesse caso não há outro envelope, e sim reavaliação.
        if (
            existing is None
            or existing[0] == operation.operation_id
            or existing[1] != operation.intent_digest
        ):
            return None
        previous = self.repository.get_result(existing[0])
        if previous is None:
            return None
        return SynchronizationResult(
            operation_id=operation.operation_id,
            batch_id=batch.batch_id,
            organization_id=operation.organization_id,
            attempt=attempt,
            status=SynchronizationResultStatus.DUPLICADA,
            decided_at=received_at,
            reason_codes=("INTENCAO_JA_SINCRONIZADA",),
            produced_references=previous.produced_references,
            limitations=(
                f"Resultado recuperado da operação {previous.operation_id.value}: "
                f"nenhum efeito foi repetido (estado anterior {previous.status.value}).",
            ),
        )

    def _idempotency_conflict(
        self,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
    ) -> SynchronizationResult | None:
        """Mesma chave com intenção diferente é conflito, nunca recuperação.

        Associar o resultado anterior aqui devolveria ao cliente a confirmação de
        um comando que ele não enviou.
        """
        existing = self.repository.find_by_idempotency_key(
            operation.organization_id, operation.idempotency_key
        )
        if existing is None or existing[1] == operation.intent_digest:
            return None
        return SynchronizationResult(
            operation_id=operation.operation_id,
            batch_id=batch.batch_id,
            organization_id=operation.organization_id,
            attempt=attempt,
            status=SynchronizationResultStatus.CONFLITANTE,
            decided_at=received_at,
            reason_codes=(
                SynchronizationConflictReason.IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE.value,
            ),
            conflict=SynchronizationConflict(
                operation_id=operation.operation_id,
                reason=(SynchronizationConflictReason.IDEMPOTENCY_KEY_COM_INTENCAO_DIVERGENTE),
                observed_state=(
                    f"A IdempotencyKey já pertence à operação {existing[0].value}, "
                    "com intenção semanticamente diferente."
                ),
                detected_at=received_at,
                alternatives=(
                    "Reenviar a operação com IdempotencyKey própria.",
                    "Confirmar qual das duas intenções deve produzir efeito.",
                ),
            ),
        )

    def _clock_conflict(
        self,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
    ) -> SynchronizationResult | None:
        """Relógio sem confiança declarada gera conflito, não aceitação silenciosa."""
        if operation.clock.confidence is not TimeConfidenceLevel.INDETERMINADO:
            return None
        return SynchronizationResult(
            operation_id=operation.operation_id,
            batch_id=batch.batch_id,
            organization_id=operation.organization_id,
            attempt=attempt,
            status=SynchronizationResultStatus.CONFLITANTE,
            decided_at=received_at,
            reason_codes=(SynchronizationConflictReason.RELOGIO_INSUFICIENTE.value,),
            conflict=SynchronizationConflict(
                operation_id=operation.operation_id,
                reason=SynchronizationConflictReason.RELOGIO_INSUFICIENTE,
                observed_state=(
                    "O Device não sustentou confiança temporal para o horário alegado."
                ),
                detected_at=received_at,
                alternatives=(
                    "Reenviar após sincronizar o relógio com o servidor.",
                    "Confirmar o horário do fato por Evidence independente.",
                ),
            ),
        )

    def _dependency_result(
        self,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
        decided: dict[TypedId, SynchronizationResultStatus],
        in_batch: dict[TypedId, OfflineOperation],
    ) -> SynchronizationResult | None:
        """Dependência ausente, recusada ou cíclica mantém estado explícito."""
        cycle = self._cycle_members(operation, in_batch)
        if cycle:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=SynchronizationResultStatus.CONFLITANTE,
                decided_at=received_at,
                reason_codes=(SynchronizationConflictReason.DEPENDENCIA_CICLICA.value,),
                conflict=SynchronizationConflict(
                    operation_id=operation.operation_id,
                    reason=SynchronizationConflictReason.DEPENDENCIA_CICLICA,
                    observed_state=(
                        "As dependências declaradas formam um ciclo e nunca seriam "
                        "satisfeitas: " + ", ".join(sorted(str(i.value) for i in cycle))
                    ),
                    detected_at=received_at,
                    alternatives=(
                        "Reenviar as operações com dependências acíclicas.",
                        "Declarar qual operação do ciclo é a origem.",
                    ),
                ),
            )

        pending: list[TypedId] = []
        reasons: list[str] = []
        for dependency in operation.depends_on:
            status = decided.get(dependency)
            if status is None:
                stored = self.repository.get_result(dependency)
                status = stored.status if stored is not None else None
            if status in (
                SynchronizationResultStatus.ACEITA,
                SynchronizationResultStatus.DUPLICADA,
            ):
                continue
            pending.append(dependency)
            reasons.append(
                "DEPENDENCIA_DESCONHECIDA" if status is None else f"DEPENDENCIA_{status.value}"
            )

        if not pending:
            return None
        return SynchronizationResult(
            operation_id=operation.operation_id,
            batch_id=batch.batch_id,
            organization_id=operation.organization_id,
            attempt=attempt,
            status=SynchronizationResultStatus.DEPENDENCIA_PENDENTE,
            decided_at=received_at,
            reason_codes=tuple(dict.fromkeys(reasons)),
            pending_dependencies=tuple(pending),
            limitations=(
                "A operação não produz efeito antes das dependências aceitas; "
                "dependência recusada permanece explícita e não é tratada como inexistente.",
            ),
        )

    @staticmethod
    def _cycle_members(
        operation: OfflineOperation, in_batch: dict[TypedId, OfflineOperation]
    ) -> set[TypedId]:
        """Descobre se a operação participa de um ciclo dentro do próprio lote."""
        seen: set[TypedId] = set()
        stack = list(operation.depends_on)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            dependency = in_batch.get(current)
            if dependency is not None:
                stack.extend(dependency.depends_on)
        return seen if operation.operation_id in seen else set()

    def _apply_effect(
        self,
        operation: OfflineOperation,
        batch: SynchronizationBatch,
        attempt: int,
        received_at: datetime,
    ) -> SynchronizationResult:
        """Produz o efeito oficial e o resultado recuperável na mesma fronteira."""
        try:
            produced = self.effect_handler(operation)
        except OfficialEffectRejected as rejection:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=SynchronizationResultStatus.REJEITADA,
                decided_at=received_at,
                reason_codes=rejection.reason_codes,
                limitations=(
                    "A rejeição não apaga a captura nem prova fraude; a operação "
                    "permanece auditável.",
                ),
            )
        except OfficialEffectConflict as conflict:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=SynchronizationResultStatus.CONFLITANTE,
                decided_at=received_at,
                reason_codes=(conflict.reason.value,),
                conflict=SynchronizationConflict(
                    operation_id=operation.operation_id,
                    reason=conflict.reason,
                    observed_state=conflict.observed_state,
                    detected_at=received_at,
                    alternatives=conflict.alternatives,
                ),
            )
        except OfficialEffectResultUnknown as unknown:
            return SynchronizationResult(
                operation_id=operation.operation_id,
                batch_id=batch.batch_id,
                organization_id=operation.organization_id,
                attempt=attempt,
                status=SynchronizationResultStatus.RESULTADO_DESCONHECIDO,
                decided_at=received_at,
                reason_codes=("RESULTADO_NAO_CONFIRMADO",),
                reconciliation_deadline=received_at + self.reconciliation_window,
                limitations=(
                    unknown.observed_state,
                    "O estado não implica ausência, sucesso ou falha e exige reconciliação.",
                ),
            )

        if not produced:
            raise ValueError(
                "Efeito oficial sem referência produzida não é recuperável: "
                "o handler deve devolver o que criou ou sinalizar rejeição."
            )
        return SynchronizationResult(
            operation_id=operation.operation_id,
            batch_id=batch.batch_id,
            organization_id=operation.organization_id,
            attempt=attempt,
            status=SynchronizationResultStatus.ACEITA,
            decided_at=received_at,
            produced_references=produced,
        )
