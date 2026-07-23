"""Modelo de domínio imutável para Recall (Passo 7.4).

Navegação retrospectiva e prospectiva pela genealogia para identificar sujeitos e
decisões **potencialmente afetados**. O resultado nunca declara invalidade, culpa,
fraude, obrigatoriedade ou extensão final de recall: ele localiza e explica.

Resultado incompleto é marcado como inconclusivo. Silêncio sobre uma lacuna seria
pior que a lacuna, porque transformaria desconhecimento em falsa cobertura.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _required_reference(data: Mapping[str, Any] | None) -> UniversalReference:
    reference = reference_from_dict(data)
    if reference is None:
        raise ValueError("Referência obrigatória ausente na desserialização do recall.")
    return reference


class RecallDirection(Enum):
    RETROSPECTIVA = "retrospectiva"
    PROSPECTIVA = "prospectiva"
    AMBAS = "ambas"


class RecallMode(Enum):
    """Simulação é hipótese; incidente é ato auditável e precisa ficar registrado."""

    SIMULACAO = "simulacao"
    INCIDENTE = "incidente"


class RecallStatus(Enum):
    CONCLUSIVO = "conclusivo"
    INCONCLUSIVO = "inconclusivo"


class RecallLimitReason(Enum):
    """Por que a travessia parou antes de esgotar o grafo."""

    PROFUNDIDADE_MAXIMA = "profundidade_maxima"
    LIMITE_DE_NOS = "limite_de_nos"
    CICLO_DETECTADO = "ciclo_detectado"
    RELACAO_SEM_VIGENCIA_NA_JANELA = "relacao_sem_vigencia_na_janela"


@dataclass(frozen=True, slots=True)
class RecallGap:
    """Lacuna declarada explicitamente. Nunca é convertida em ausência de risco."""

    reason: RecallLimitReason
    at_reference: UniversalReference
    depth: int
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, RecallLimitReason):
            raise TypeError("reason deve ser um RecallLimitReason válido.")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError("Toda lacuna exige descrição explícita.")


@dataclass(frozen=True, slots=True)
class RecallStep:
    """Uma aresta percorrida, com a relação que a justifica."""

    relation_id: TypedId
    relation_type: str
    from_reference: UniversalReference
    to_reference: UniversalReference
    direction: RecallDirection


@dataclass(frozen=True, slots=True)
class RecallPath:
    """Caminho explicável da origem até um sujeito alcançado."""

    steps: tuple[RecallStep, ...]

    @property
    def reached(self) -> UniversalReference:
        if not self.steps:
            raise ValueError("Caminho vazio não alcança sujeito algum.")
        return self.steps[-1].to_reference

    @property
    def depth(self) -> int:
        return len(self.steps)

    def explain(self) -> str:
        """Descrição legível do caminho, para justificar por que o sujeito entrou."""
        partes = [
            f"{s.from_reference.target_id.entity_type}:{s.from_reference.target_id.value}"
            f" --[{s.relation_type}]--> "
            f"{s.to_reference.target_id.entity_type}:{s.to_reference.target_id.value}"
            for s in self.steps
        ]
        return " | ".join(partes)


@dataclass(frozen=True, slots=True)
class RecallRequest:
    organization_id: OrganizationId
    subject_reference: UniversalReference
    direction: RecallDirection
    mode: RecallMode
    at_time: datetime | None = None
    max_depth: int = 5
    max_nodes: int = 500
    relation_types: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.subject_reference, UniversalReference):
            raise TypeError("subject_reference deve ser uma UniversalReference.")
        if not isinstance(self.direction, RecallDirection):
            raise TypeError("direction deve ser um RecallDirection válido.")
        if not isinstance(self.mode, RecallMode):
            raise TypeError("mode deve ser um RecallMode válido.")
        if not isinstance(self.max_depth, int) or self.max_depth < 1:
            raise ValueError("max_depth deve ser um número inteiro >= 1.")
        if not isinstance(self.max_nodes, int) or self.max_nodes < 1:
            raise ValueError("max_nodes deve ser um número inteiro >= 1.")
        if (
            self.subject_reference.organization_id is not None
            and self.subject_reference.organization_id != self.organization_id
        ):
            raise ValueError(
                "O Subject inicial pertence a outra Organization: recall não "
                "atravessa fronteira de tenant."
            )


@dataclass(frozen=True, slots=True)
class RecallResult:
    """Resultado explicável. Sujeitos alcançados são POTENCIALMENTE afetados.

    Isso indica necessidade potencial de revisão. Não significa inválido e não
    modifica Decision, Dossier, assinatura ou Evidence alguma.
    """

    recall_id: TypedId
    request: RecallRequest
    executed_at: datetime
    paths: tuple[RecallPath, ...] = field(default_factory=tuple)
    gaps: tuple[RecallGap, ...] = field(default_factory=tuple)
    affected_decision_ids: tuple[TypedId, ...] = field(default_factory=tuple)
    visited_nodes: int = 0

    def __post_init__(self) -> None:
        if self.recall_id.entity_type != "recall":
            raise ValueError("recall_id deve ser do tipo 'recall'.")
        if not isinstance(self.request, RecallRequest):
            raise TypeError("request deve ser um RecallRequest.")

    @property
    def status(self) -> RecallStatus:
        """Qualquer lacuna torna o resultado inconclusivo, sem exceção."""
        return RecallStatus.INCONCLUSIVO if self.gaps else RecallStatus.CONCLUSIVO

    @property
    def is_conclusive(self) -> bool:
        return self.status is RecallStatus.CONCLUSIVO

    def affected_subjects(self) -> tuple[UniversalReference, ...]:
        """Sujeitos alcançados, sem repetição e em ordem determinística."""
        vistos: list[UniversalReference] = []
        for path in self.paths:
            alcancado = path.reached
            if alcancado not in vistos:
                vistos.append(alcancado)
        return tuple(vistos)

    def paths_to(self, reference: UniversalReference) -> tuple[RecallPath, ...]:
        return tuple(p for p in self.paths if p.reached == reference)

    def explain_gaps(self) -> tuple[str, ...]:
        return tuple(f"{g.reason.value}: {g.description}" for g in self.gaps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recall_id": str(self.recall_id.value),
            "executed_at": self.executed_at.isoformat(),
            "visited_nodes": self.visited_nodes,
            "status": self.status.value,
            "request": {
                "organization_id": str(self.request.organization_id.value),
                "subject_reference": reference_to_dict(self.request.subject_reference),
                "direction": self.request.direction.value,
                "mode": self.request.mode.value,
                "at_time": (self.request.at_time.isoformat() if self.request.at_time else None),
                "max_depth": self.request.max_depth,
                "max_nodes": self.request.max_nodes,
                "relation_types": list(self.request.relation_types),
            },
            "paths": [
                [
                    {
                        "relation_id": str(s.relation_id.value),
                        "relation_type": s.relation_type,
                        "from_reference": reference_to_dict(s.from_reference),
                        "to_reference": reference_to_dict(s.to_reference),
                        "direction": s.direction.value,
                    }
                    for s in path.steps
                ]
                for path in self.paths
            ],
            "gaps": [
                {
                    "reason": g.reason.value,
                    "at_reference": reference_to_dict(g.at_reference),
                    "depth": g.depth,
                    "description": g.description,
                }
                for g in self.gaps
            ],
            "affected_decision_ids": [str(d.value) for d in self.affected_decision_ids],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RecallResult":
        raw_request = data["request"]
        request = RecallRequest(
            organization_id=OrganizationId(UUID(raw_request["organization_id"])),
            subject_reference=_required_reference(raw_request["subject_reference"]),
            direction=RecallDirection(raw_request["direction"]),
            mode=RecallMode(raw_request["mode"]),
            at_time=(
                datetime.fromisoformat(raw_request["at_time"])
                if raw_request.get("at_time")
                else None
            ),
            max_depth=raw_request["max_depth"],
            max_nodes=raw_request["max_nodes"],
            relation_types=tuple(raw_request.get("relation_types", [])),
        )
        return cls(
            recall_id=TypedId(entity_type="recall", value=UUID(data["recall_id"])),
            request=request,
            executed_at=datetime.fromisoformat(data["executed_at"]),
            paths=tuple(
                RecallPath(
                    steps=tuple(
                        RecallStep(
                            relation_id=TypedId(
                                entity_type="relation", value=UUID(s["relation_id"])
                            ),
                            relation_type=s["relation_type"],
                            from_reference=_required_reference(s["from_reference"]),
                            to_reference=_required_reference(s["to_reference"]),
                            direction=RecallDirection(s["direction"]),
                        )
                        for s in raw_path
                    )
                )
                for raw_path in data.get("paths", [])
            ),
            gaps=tuple(
                RecallGap(
                    reason=RecallLimitReason(g["reason"]),
                    at_reference=_required_reference(g["at_reference"]),
                    depth=g["depth"],
                    description=g["description"],
                )
                for g in data.get("gaps", [])
            ),
            affected_decision_ids=tuple(
                TypedId(entity_type="decision", value=UUID(d))
                for d in data.get("affected_decision_ids", [])
            ),
            visited_nodes=data.get("visited_nodes", 0),
        )


def build_paths_from_steps(sequences: Sequence[Sequence[RecallStep]]) -> tuple[RecallPath, ...]:
    return tuple(RecallPath(steps=tuple(seq)) for seq in sequences if seq)
