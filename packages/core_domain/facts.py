"""Modelo de domínio imutável para Contrato de Fatos da Vertical (ADR-0038/Passo 6.3)."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def reference_to_dict(reference: UniversalReference | None) -> dict[str, Any] | None:
    if reference is None:
        return None
    org = reference.organization_id
    return {
        "entity_type": reference.target_id.entity_type,
        "value": str(reference.target_id.value),
        "organization_id": str(org.value) if org is not None else None,
        "contract_version": reference.contract_version,
    }


def reference_from_dict(data: Mapping[str, Any] | None) -> UniversalReference | None:
    if data is None:
        return None
    org_raw = data.get("organization_id")
    return UniversalReference(
        target_id=TypedId(entity_type=data["entity_type"], value=UUID(data["value"])),
        organization_id=OrganizationId(UUID(org_raw)) if org_raw is not None else None,
        contract_version=data["contract_version"],
    )


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: TypedId
    fact_type: str
    payload: dict[str, Any]
    observed_at: datetime
    source_reference: UniversalReference | None = None
    recorded_at: datetime | None = None
    known_at: datetime | None = None
    discovered_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.fact_id.entity_type != "fact":
            raise ValueError("fact_id deve ser do tipo 'fact'.")
        if not isinstance(self.fact_type, str) or not self.fact_type.strip():
            raise ValueError("fact_type deve ser uma string não vazia.")
        if not isinstance(self.payload, dict):
            raise TypeError("payload deve ser um dicionário.")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at deve ser um datetime.")
        for field_name in ("recorded_at", "known_at", "discovered_at"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, datetime):
                raise TypeError(f"{field_name} deve ser um datetime ou None.")

    @classmethod
    def create(
        cls,
        fact_type: str,
        payload: dict[str, Any],
        observed_at: datetime,
        source_reference: UniversalReference | None = None,
        recorded_at: datetime | None = None,
        known_at: datetime | None = None,
        discovered_at: datetime | None = None,
    ) -> "Fact":
        return cls(
            fact_id=TypedId.new("fact"),
            fact_type=fact_type.strip().lower(),
            payload=dict(payload),
            observed_at=observed_at,
            source_reference=source_reference,
            recorded_at=recorded_at,
            known_at=known_at,
            discovered_at=discovered_at,
        )

    def effective_known_at(self) -> datetime:
        """Instante usado pelo snapshot para cortar conhecimento admissível.

        Enquanto a modelagem histórica completa do ADR-0052 não existir em todas
        as fontes, o Titan usa `known_at`, depois `recorded_at`, e por fim
        `observed_at` como fallback explícito para preservar compatibilidade.
        """
        return self.known_at or self.recorded_at or self.observed_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": str(self.fact_id.value),
            "fact_type": self.fact_type,
            "payload": self.payload,
            "observed_at": self.observed_at.isoformat(),
            "source_reference": reference_to_dict(self.source_reference),
            "recorded_at": None if self.recorded_at is None else self.recorded_at.isoformat(),
            "known_at": None if self.known_at is None else self.known_at.isoformat(),
            "discovered_at": (
                None if self.discovered_at is None else self.discovered_at.isoformat()
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Fact":
        return cls(
            fact_id=TypedId(entity_type="fact", value=UUID(data["fact_id"])),
            fact_type=data["fact_type"],
            payload=dict(data["payload"]),
            observed_at=datetime.fromisoformat(data["observed_at"]),
            source_reference=reference_from_dict(data.get("source_reference")),
            recorded_at=(
                None
                if data.get("recorded_at") is None
                else datetime.fromisoformat(data["recorded_at"])
            ),
            known_at=(
                None if data.get("known_at") is None else datetime.fromisoformat(data["known_at"])
            ),
            discovered_at=(
                None
                if data.get("discovered_at") is None
                else datetime.fromisoformat(data["discovered_at"])
            ),
        )


@dataclass(frozen=True, slots=True)
class FactSnapshot:
    organization_id: OrganizationId
    target_id: TypedId
    as_of: datetime
    facts: tuple[Fact, ...] = field(default_factory=tuple)
    snapshot_hash: str = ""
    reference_time: datetime | None = None
    knowledge_cutoff: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.target_id, TypedId):
            raise TypeError("target_id deve ser TypedId.")
        if not isinstance(self.as_of, datetime):
            raise TypeError("as_of deve ser datetime.")
        if not isinstance(self.facts, tuple):
            raise TypeError("facts deve ser uma tupla.")
        if self.reference_time is not None and not isinstance(self.reference_time, datetime):
            raise TypeError("reference_time deve ser datetime ou None.")
        if self.knowledge_cutoff is not None and not isinstance(self.knowledge_cutoff, datetime):
            raise TypeError("knowledge_cutoff deve ser datetime ou None.")

    def effective_reference_time(self) -> datetime:
        return self.reference_time or self.as_of

    def effective_knowledge_cutoff(self) -> datetime:
        return self.knowledge_cutoff or self.as_of

    def get_facts_by_type(self, fact_type: str) -> tuple[Fact, ...]:
        clean_type = fact_type.strip().lower()
        return tuple(f for f in self.facts if f.fact_type == clean_type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": str(self.organization_id.value),
            "target_id": {
                "entity_type": self.target_id.entity_type,
                "value": str(self.target_id.value),
            },
            "as_of": self.as_of.isoformat(),
            "reference_time": self.effective_reference_time().isoformat(),
            "knowledge_cutoff": self.effective_knowledge_cutoff().isoformat(),
            "facts": [f.to_dict() for f in self.facts],
            "snapshot_hash": self.snapshot_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FactSnapshot":
        """Restaura o snapshot preservando o hash original, sem recalculá-lo.

        Recalcular apagaria a evidência de que a avaliação histórica foi feita
        exatamente sobre estes fatos.
        """
        target = data["target_id"]
        return cls(
            organization_id=OrganizationId(UUID(data["organization_id"])),
            target_id=TypedId(entity_type=target["entity_type"], value=UUID(target["value"])),
            as_of=datetime.fromisoformat(data["as_of"]),
            facts=tuple(Fact.from_dict(item) for item in data["facts"]),
            snapshot_hash=data["snapshot_hash"],
            reference_time=(
                None
                if data.get("reference_time") is None
                else datetime.fromisoformat(data["reference_time"])
            ),
            knowledge_cutoff=(
                None
                if data.get("knowledge_cutoff") is None
                else datetime.fromisoformat(data["knowledge_cutoff"])
            ),
        )

    def get_latest_fact_by_type(self, fact_type: str) -> Fact | None:
        matching = self.get_facts_by_type(fact_type)
        if not matching:
            return None
        return max(matching, key=lambda f: f.observed_at)

    @classmethod
    def create(
        cls,
        organization_id: OrganizationId,
        target_id: TypedId,
        as_of: datetime,
        facts: Sequence[Fact],
        reference_time: datetime | None = None,
        knowledge_cutoff: datetime | None = None,
    ) -> "FactSnapshot":
        resolved_reference_time = reference_time or as_of
        resolved_knowledge_cutoff = knowledge_cutoff or as_of
        selected_facts = tuple(
            fact for fact in facts if fact.effective_known_at() <= resolved_knowledge_cutoff
        )
        sorted_facts = tuple(
            sorted(selected_facts, key=lambda f: (f.fact_type, f.observed_at, f.fact_id.value))
        )

        # Cálculo determinístico de hash do snapshot
        hash_payload = {
            "organization_id": str(organization_id.value),
            "target_id": {
                "entity_type": target_id.entity_type,
                "value": str(target_id.value),
            },
            "as_of": as_of.isoformat(),
            "reference_time": resolved_reference_time.isoformat(),
            "knowledge_cutoff": resolved_knowledge_cutoff.isoformat(),
            "facts": [
                {
                    "fact_id": str(f.fact_id.value),
                    "fact_type": f.fact_type,
                    "payload": f.payload,
                    "observed_at": f.observed_at.isoformat(),
                    "source_reference": reference_to_dict(f.source_reference),
                    "recorded_at": (None if f.recorded_at is None else f.recorded_at.isoformat()),
                    "known_at": None if f.known_at is None else f.known_at.isoformat(),
                    "discovered_at": (
                        None if f.discovered_at is None else f.discovered_at.isoformat()
                    ),
                }
                for f in sorted_facts
            ],
        }
        raw_bytes = json.dumps(hash_payload, sort_keys=True).encode("utf-8")
        calc_hash = hashlib.sha256(raw_bytes).hexdigest()

        return cls(
            organization_id=organization_id,
            target_id=target_id,
            as_of=as_of,
            facts=sorted_facts,
            snapshot_hash=calc_hash,
            reference_time=resolved_reference_time,
            knowledge_cutoff=resolved_knowledge_cutoff,
        )
