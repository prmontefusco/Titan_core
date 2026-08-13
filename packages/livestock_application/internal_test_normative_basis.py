"""Catálogo controlado de bases normativas exclusivamente sintéticas.

O contrato existe para provar a seleção temporal de ``MARKET_TEST_A`` sem
atribuir autoridade, oficialidade ou reconhecimento externo ao material.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.core_domain.normative import (
    NormativeBasisSnapshot,
    NormativeReferenceSnapshot,
    NormativeSourceClassification,
)
from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc

MARKET_TEST_A_CODE = "MARKET_TEST_A"
MARKET_TEST_A_PURPOSE = "market-test-a"
_INTERNAL_TEST_JURISDICTION = "INTERNAL_TEST"
_INTERNAL_TEST_INTENDED_USE = "INTERNAL_TEST_ONLY"
_INTERNAL_TEST_APPROVAL_AUTHORITY = "INTERNAL_TEST_ONLY"
_RECOGNITION_LIMITATION = "RECOGNITION_BOUNDARY:INTERNAL_ONLY"
_RESULT_LIMITATION = "MARKET_ELIGIBILITY_ASSESSMENT_NOT_EXPORT_AUTHORIZATION"


@dataclass(frozen=True, slots=True)
class InternalTestNormativeBasis:
    """Material versionado do catálogo sintético, sem semântica de mercado real."""

    normative_basis_id: TypedId
    organization_id: OrganizationId
    code: str
    version: int
    policy_id: TypedId
    policy_code: str
    policy_version: int
    purpose: str
    valid_from: datetime
    valid_until: datetime | None
    known_at: datetime
    approved_by: str
    approved_at: datetime
    instrument_code: str
    instrument_version: str
    provision: str | None
    content_digest: str
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.normative_basis_id.entity_type != "normative_basis":
            raise ValueError("normative_basis_id deve ser do tipo 'normative_basis'.")
        if self.policy_id.entity_type != "policy":
            raise ValueError("policy_id deve ser do tipo 'policy'.")
        for field_name in (
            "code",
            "policy_code",
            "purpose",
            "approved_by",
            "instrument_code",
            "instrument_version",
            "content_digest",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser uma string não vazia.")
        if self.provision is not None and not self.provision.strip():
            raise ValueError("provision, quando informado, não pode ser vazio.")
        if len(self.content_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.content_digest.lower()
        ):
            raise ValueError("content_digest deve ser um digest SHA-256 hexadecimal.")
        for field_name in ("version", "policy_version"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} deve ser inteiro >= 1.")
        for field_name in ("valid_from", "known_at", "approved_at"):
            require_utc(getattr(self, field_name), field_name=field_name)
        if self.valid_until is not None:
            require_utc(self.valid_until, field_name="valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError(
                    "valid_until deve ser posterior a valid_from em intervalo semiaberto."
                )
        if self.approved_at > self.known_at:
            raise ValueError("approved_at não pode ser posterior a known_at.")
        if any(not value.strip() for value in self.limitations):
            raise ValueError("limitations não pode conter textos vazios.")

    def applies_at(self, reference_time: datetime) -> bool:
        require_utc(reference_time, field_name="reference_time")
        return self.valid_from <= reference_time and (
            self.valid_until is None or reference_time < self.valid_until
        )

    def known_as_of(self, knowledge_cutoff: datetime) -> bool:
        require_utc(knowledge_cutoff, field_name="knowledge_cutoff")
        return self.known_at <= knowledge_cutoff

    def to_snapshot(
        self,
        *,
        policy: Policy,
        rules: tuple[Rule, ...],
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> NormativeBasisSnapshot:
        return NormativeBasisSnapshot(
            schema_version=1,
            normative_basis_id=self.normative_basis_id,
            normative_basis_code=self.code,
            normative_basis_version=self.version,
            policy_id=policy.policy_id,
            policy_code=policy.code,
            policy_version=policy.version,
            rule_versions=tuple((rule.code, rule.version) for rule in rules),
            purpose=self.purpose,
            jurisdiction=_INTERNAL_TEST_JURISDICTION,
            intended_use=_INTERNAL_TEST_INTENDED_USE,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
            approved_by=self.approved_by,
            approval_authority=_INTERNAL_TEST_APPROVAL_AUTHORITY,
            approved_at=self.approved_at,
            references=(
                NormativeReferenceSnapshot(
                    instrument_code=self.instrument_code,
                    instrument_version=self.instrument_version,
                    provision=self.provision,
                    content_digest=self.content_digest,
                    digest_algorithm="sha256",
                    source_classification=NormativeSourceClassification.INTERNAL_TEST,
                ),
            ),
            limitations=tuple(
                dict.fromkeys(self.limitations + (_RECOGNITION_LIMITATION, _RESULT_LIMITATION))
            ),
        )


class InternalTestNormativeBasisRepositoryPort(Protocol):
    def save(self, item: InternalTestNormativeBasis) -> None: ...

    def list_by_policy(
        self, organization_id: OrganizationId, policy_id: TypedId
    ) -> list[InternalTestNormativeBasis]: ...


@dataclass(frozen=True, slots=True)
class PersistedInternalTestNormativeBasisSnapshotProvider:
    """Seleciona exatamente uma base sintética elegível; ausência ou conflito falha fechada."""

    repository: InternalTestNormativeBasisRepositoryPort

    def select(
        self,
        *,
        policy: Policy,
        rules: tuple[Rule, ...],
        purpose: str,
        reference_time: datetime,
        knowledge_cutoff: datetime,
    ) -> NormativeBasisSnapshot | None:
        if (
            policy.code != MARKET_TEST_A_CODE
            or purpose != MARKET_TEST_A_PURPOSE
            or not rules
            or any(rule.policy_id != policy.policy_id for rule in rules)
        ):
            return None
        candidates = [
            item
            for item in self.repository.list_by_policy(policy.organization_id, policy.policy_id)
            if item.policy_code == policy.code
            and item.policy_version == policy.version
            and item.purpose == purpose
            and item.applies_at(reference_time)
            and item.known_as_of(knowledge_cutoff)
        ]
        if len(candidates) != 1:
            return None
        return candidates[0].to_snapshot(
            policy=policy,
            rules=rules,
            reference_time=reference_time,
            knowledge_cutoff=knowledge_cutoff,
        )
