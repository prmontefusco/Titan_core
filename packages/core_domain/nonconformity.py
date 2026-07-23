"""Modelo de domínio imutável para NonConformity (Passo 7.3).

Registro auditável de falha, lacuna ou condição que exige tratamento. O ciclo de
vida avança por transições explícitas e **encerramento nunca remove histórico**:
cada mudança de estado é acrescentada, jamais sobrescrita.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from packages.core_domain.evidence import ValidityPeriod
from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.core_domain.rule import SeverityLevel
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class NonConformityStatus(Enum):
    DETECTADA = "detectada"
    CLASSIFICADA = "classificada"
    ATRIBUIDA = "atribuida"
    EM_CORRECAO = "em_correcao"
    PRONTA_PARA_REAVALIACAO = "pronta_para_reavaliacao"
    ENCERRADA = "encerrada"


class NonConformityOrigin(Enum):
    """De onde veio a não conformidade. Origem é registro, não interpretação."""

    REGRA_NAO_ATENDIDA = "regra_nao_atendida"
    EVIDENCIA_AUSENTE = "evidencia_ausente"
    EVIDENCIA_INVALIDA = "evidencia_invalida"
    DIVERGENCIA_ENTRE_FONTES = "divergencia_entre_fontes"
    SEQUENCIA_IMPOSSIVEL = "sequencia_impossivel"
    QUEBRA_DE_INTEGRIDADE = "quebra_de_integridade"
    CONFLITO_DE_SINCRONIZACAO = "conflito_de_sincronizacao"
    DESCUMPRIMENTO_DE_PROCESSO = "descumprimento_de_processo"


# Reavaliação reprovada devolve o caso à correção: é o único retorno permitido, e
# existe porque corrigir nem sempre resolve na primeira tentativa.
_ALLOWED_TRANSITIONS: dict[NonConformityStatus, frozenset[NonConformityStatus]] = {
    NonConformityStatus.DETECTADA: frozenset({NonConformityStatus.CLASSIFICADA}),
    NonConformityStatus.CLASSIFICADA: frozenset({NonConformityStatus.ATRIBUIDA}),
    NonConformityStatus.ATRIBUIDA: frozenset({NonConformityStatus.EM_CORRECAO}),
    NonConformityStatus.EM_CORRECAO: frozenset({NonConformityStatus.PRONTA_PARA_REAVALIACAO}),
    NonConformityStatus.PRONTA_PARA_REAVALIACAO: frozenset(
        {NonConformityStatus.ENCERRADA, NonConformityStatus.EM_CORRECAO}
    ),
    NonConformityStatus.ENCERRADA: frozenset(),
}


@dataclass(frozen=True, slots=True)
class NonConformityTransition:
    """Entrada imutável do histórico. Nunca é alterada nem removida."""

    from_status: NonConformityStatus | None
    to_status: NonConformityStatus
    occurred_at: datetime
    note: str = ""
    actor_reference: UniversalReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.to_status, NonConformityStatus):
            raise TypeError("to_status deve ser um NonConformityStatus válido.")
        if not isinstance(self.occurred_at, datetime):
            raise TypeError("occurred_at deve ser um datetime.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_status": self.from_status.value if self.from_status else None,
            "to_status": self.to_status.value,
            "occurred_at": self.occurred_at.isoformat(),
            "note": self.note,
            "actor_reference": reference_to_dict(self.actor_reference),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NonConformityTransition":
        raw_from = data.get("from_status")
        return cls(
            from_status=NonConformityStatus(raw_from) if raw_from else None,
            to_status=NonConformityStatus(data["to_status"]),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            note=data.get("note", ""),
            actor_reference=reference_from_dict(data.get("actor_reference")),
        )


@dataclass(frozen=True, slots=True)
class NonConformity:
    nonconformity_id: TypedId
    organization_id: OrganizationId
    subject_reference: UniversalReference
    origin: NonConformityOrigin
    severity: SeverityLevel
    description: str
    detected_at: datetime
    status: NonConformityStatus = NonConformityStatus.DETECTADA
    affected_period: ValidityPeriod = field(default_factory=ValidityPeriod)
    origin_reference: UniversalReference | None = None
    responsible_reference: UniversalReference | None = None
    due_date: datetime | None = None
    corrective_action: str = ""
    correction_evidence_references: tuple[UniversalReference, ...] = field(default_factory=tuple)
    reevaluation_id: TypedId | None = None
    closed_at: datetime | None = None
    closure_note: str = ""
    transitions: tuple[NonConformityTransition, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.nonconformity_id.entity_type != "nonconformity":
            raise ValueError("nonconformity_id deve ser do tipo 'nonconformity'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.subject_reference, UniversalReference):
            raise TypeError("subject_reference deve ser uma UniversalReference.")
        if not isinstance(self.origin, NonConformityOrigin):
            raise TypeError("origin deve ser um NonConformityOrigin válido.")
        if not isinstance(self.severity, SeverityLevel):
            raise TypeError("severity deve ser um SeverityLevel válido.")
        if not isinstance(self.status, NonConformityStatus):
            raise TypeError("status deve ser um NonConformityStatus válido.")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Toda NonConformity exige descrição não vazia.")
        if not isinstance(self.transitions, tuple):
            raise TypeError("transitions deve ser uma tupla.")
        if (
            self.subject_reference.organization_id is not None
            and self.subject_reference.organization_id != self.organization_id
        ):
            raise ValueError("O Subject da não conformidade pertence a outra Organization.")
        if self.status is NonConformityStatus.ENCERRADA and self.closed_at is None:
            raise ValueError("Não conformidade encerrada exige instante de encerramento.")

    # -- Consultas ---------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self.status is NonConformityStatus.ENCERRADA

    def history(self) -> tuple[NonConformityTransition, ...]:
        return self.transitions

    # -- Transições --------------------------------------------------------

    def _advance(
        self,
        to_status: NonConformityStatus,
        occurred_at: datetime,
        note: str = "",
        actor_reference: UniversalReference | None = None,
        **changes: Any,
    ) -> "NonConformity":
        allowed = _ALLOWED_TRANSITIONS[self.status]
        if to_status not in allowed:
            raise ValueError(
                f"Transição inválida: '{self.status.value}' não pode ir para '{to_status.value}'."
            )

        transition = NonConformityTransition(
            from_status=self.status,
            to_status=to_status,
            occurred_at=occurred_at,
            note=note,
            actor_reference=actor_reference,
        )
        base: dict[str, Any] = {
            "nonconformity_id": self.nonconformity_id,
            "organization_id": self.organization_id,
            "subject_reference": self.subject_reference,
            "origin": self.origin,
            "severity": self.severity,
            "description": self.description,
            "detected_at": self.detected_at,
            "status": to_status,
            "affected_period": self.affected_period,
            "origin_reference": self.origin_reference,
            "responsible_reference": self.responsible_reference,
            "due_date": self.due_date,
            "corrective_action": self.corrective_action,
            "correction_evidence_references": self.correction_evidence_references,
            "reevaluation_id": self.reevaluation_id,
            "closed_at": self.closed_at,
            "closure_note": self.closure_note,
            # O histórico só cresce.
            "transitions": (*self.transitions, transition),
        }
        base.update(changes)
        return NonConformity(**base)

    def classify(
        self,
        occurred_at: datetime,
        severity: SeverityLevel | None = None,
        corrective_action: str = "",
        affected_period: ValidityPeriod | None = None,
        note: str = "",
    ) -> "NonConformity":
        return self._advance(
            NonConformityStatus.CLASSIFICADA,
            occurred_at,
            note=note,
            severity=severity or self.severity,
            corrective_action=corrective_action or self.corrective_action,
            affected_period=affected_period or self.affected_period,
        )

    def assign(
        self,
        responsible_reference: UniversalReference,
        due_date: datetime,
        occurred_at: datetime,
        note: str = "",
    ) -> "NonConformity":
        if (
            responsible_reference.organization_id is not None
            and responsible_reference.organization_id != self.organization_id
        ):
            raise ValueError("O responsável pertence a outra Organization.")
        return self._advance(
            NonConformityStatus.ATRIBUIDA,
            occurred_at,
            note=note,
            responsible_reference=responsible_reference,
            due_date=due_date,
        )

    def start_correction(self, occurred_at: datetime, note: str = "") -> "NonConformity":
        return self._advance(NonConformityStatus.EM_CORRECAO, occurred_at, note=note)

    def submit_for_reevaluation(
        self,
        correction_evidence_references: Sequence[UniversalReference],
        occurred_at: datetime,
        note: str = "",
    ) -> "NonConformity":
        # Correção sem prova não é correção: seria encerrar por declaração.
        if not correction_evidence_references:
            raise ValueError("A reavaliação exige ao menos uma evidência de correção.")
        return self._advance(
            NonConformityStatus.PRONTA_PARA_REAVALIACAO,
            occurred_at,
            note=note,
            correction_evidence_references=(
                *self.correction_evidence_references,
                *correction_evidence_references,
            ),
        )

    def reject_reevaluation(self, occurred_at: datetime, note: str) -> "NonConformity":
        """A reavaliação não confirmou a correção: volta a correção, sem apagar nada."""
        if not note.strip():
            raise ValueError("Rejeitar a reavaliação exige justificativa.")
        return self._advance(NonConformityStatus.EM_CORRECAO, occurred_at, note=note)

    def close(
        self,
        reevaluation_id: TypedId,
        occurred_at: datetime,
        note: str = "",
    ) -> "NonConformity":
        if reevaluation_id.entity_type != "evaluation":
            raise ValueError("O encerramento exige a Evaluation que reavaliou o caso.")
        return self._advance(
            NonConformityStatus.ENCERRADA,
            occurred_at,
            note=note,
            reevaluation_id=reevaluation_id,
            closed_at=occurred_at,
            closure_note=note,
        )

    # -- Construção --------------------------------------------------------

    @classmethod
    def detect(
        cls,
        organization_id: OrganizationId,
        subject_reference: UniversalReference,
        origin: NonConformityOrigin,
        severity: SeverityLevel,
        description: str,
        detected_at: datetime,
        origin_reference: UniversalReference | None = None,
        affected_period: ValidityPeriod | None = None,
        corrective_action: str = "",
    ) -> "NonConformity":
        return cls(
            nonconformity_id=TypedId.new("nonconformity"),
            organization_id=organization_id,
            subject_reference=subject_reference,
            origin=origin,
            severity=severity,
            description=description.strip(),
            detected_at=detected_at,
            status=NonConformityStatus.DETECTADA,
            affected_period=affected_period or ValidityPeriod(),
            origin_reference=origin_reference,
            corrective_action=corrective_action.strip(),
            transitions=(
                NonConformityTransition(
                    from_status=None,
                    to_status=NonConformityStatus.DETECTADA,
                    occurred_at=detected_at,
                    note="Detecção registrada.",
                ),
            ),
        )

    # -- Serialização ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "nonconformity_id": str(self.nonconformity_id.value),
            "organization_id": str(self.organization_id.value),
            "subject_reference": reference_to_dict(self.subject_reference),
            "origin": self.origin.value,
            "severity": self.severity.value,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "status": self.status.value,
            "valid_from": (
                self.affected_period.valid_from.isoformat()
                if self.affected_period.valid_from
                else None
            ),
            "valid_until": (
                self.affected_period.valid_until.isoformat()
                if self.affected_period.valid_until
                else None
            ),
            "origin_reference": reference_to_dict(self.origin_reference),
            "responsible_reference": reference_to_dict(self.responsible_reference),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "corrective_action": self.corrective_action,
            "correction_evidence_references": [
                reference_to_dict(r) for r in self.correction_evidence_references
            ],
            "reevaluation_id": (str(self.reevaluation_id.value) if self.reevaluation_id else None),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "closure_note": self.closure_note,
            "transitions": [t.to_dict() for t in self.transitions],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NonConformity":
        subject = reference_from_dict(data["subject_reference"])
        if subject is None:
            raise ValueError("NonConformity exige Subject.")
        raw_reevaluation = data.get("reevaluation_id")
        return cls(
            nonconformity_id=TypedId(
                entity_type="nonconformity", value=UUID(data["nonconformity_id"])
            ),
            organization_id=OrganizationId(UUID(data["organization_id"])),
            subject_reference=subject,
            origin=NonConformityOrigin(data["origin"]),
            severity=SeverityLevel(data["severity"]),
            description=data["description"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            status=NonConformityStatus(data["status"]),
            affected_period=ValidityPeriod(
                valid_from=(
                    datetime.fromisoformat(data["valid_from"]) if data.get("valid_from") else None
                ),
                valid_until=(
                    datetime.fromisoformat(data["valid_until"]) if data.get("valid_until") else None
                ),
            ),
            origin_reference=reference_from_dict(data.get("origin_reference")),
            responsible_reference=reference_from_dict(data.get("responsible_reference")),
            due_date=(datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None),
            corrective_action=data.get("corrective_action", ""),
            correction_evidence_references=tuple(
                ref
                for ref in (
                    reference_from_dict(i) for i in data.get("correction_evidence_references", [])
                )
                if ref is not None
            ),
            reevaluation_id=(
                TypedId(entity_type="evaluation", value=UUID(raw_reevaluation))
                if raw_reevaluation
                else None
            ),
            closed_at=(
                datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None
            ),
            closure_note=data.get("closure_note", ""),
            transitions=tuple(
                NonConformityTransition.from_dict(t) for t in data.get("transitions", [])
            ),
        )
