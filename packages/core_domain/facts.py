"""Modelo de domínio imutável para Contrato de Fatos da Vertical (ADR-0038/Passo 6.3)."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: TypedId
    fact_type: str
    payload: dict[str, Any]
    observed_at: datetime
    source_reference: UniversalReference | None = None

    def __post_init__(self) -> None:
        if self.fact_id.entity_type != "fact":
            raise ValueError("fact_id deve ser do tipo 'fact'.")
        if not isinstance(self.fact_type, str) or not self.fact_type.strip():
            raise ValueError("fact_type deve ser uma string não vazia.")
        if not isinstance(self.payload, dict):
            raise TypeError("payload deve ser um dicionário.")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at deve ser um datetime.")

    @classmethod
    def create(
        cls,
        fact_type: str,
        payload: dict[str, Any],
        observed_at: datetime,
        source_reference: UniversalReference | None = None,
    ) -> "Fact":
        return cls(
            fact_id=TypedId.new("fact"),
            fact_type=fact_type.strip().lower(),
            payload=dict(payload),
            observed_at=observed_at,
            source_reference=source_reference,
        )


@dataclass(frozen=True, slots=True)
class FactSnapshot:
    organization_id: OrganizationId
    target_id: TypedId
    as_of: datetime
    facts: tuple[Fact, ...] = field(default_factory=tuple)
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.target_id, TypedId):
            raise TypeError("target_id deve ser TypedId.")
        if not isinstance(self.as_of, datetime):
            raise TypeError("as_of deve ser datetime.")
        if not isinstance(self.facts, tuple):
            raise TypeError("facts deve ser uma tupla.")

    def get_facts_by_type(self, fact_type: str) -> tuple[Fact, ...]:
        clean_type = fact_type.strip().lower()
        return tuple(f for f in self.facts if f.fact_type == clean_type)

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
    ) -> "FactSnapshot":
        sorted_facts = tuple(
            sorted(facts, key=lambda f: (f.fact_type, f.observed_at, f.fact_id.value))
        )

        # Cálculo determinístico de hash do snapshot
        hash_payload = {
            "organization_id": str(organization_id.value),
            "target_id": str(target_id.value),
            "as_of": as_of.isoformat(),
            "facts": [
                {
                    "fact_id": str(f.fact_id.value),
                    "fact_type": f.fact_type,
                    "payload": f.payload,
                    "observed_at": f.observed_at.isoformat(),
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
        )
