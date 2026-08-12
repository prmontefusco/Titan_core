"""Fotografia normativa imutável usada por uma Evaluation (ADR-0011/NEXT-02)."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Self

from packages.core_domain.events import CanonicalPayload
from packages.shared_kernel import TypedId
from packages.shared_kernel.serialization import CanonicalValue
from packages.shared_kernel.temporal import require_utc


class NormativeSourceClassification(Enum):
    """Natureza declarada da fonte, sem inferir autoridade ou admissibilidade."""

    INTERNAL_TEST = "internal_test"
    OFFICIAL = "official"
    PRIVATE = "private"


class NormativeSnapshotLimitation(Enum):
    """Limitação explícita para registros anteriores ao contrato do snapshot."""

    LEGACY_ABSENT = "NORMATIVE_BASIS_SNAPSHOT_LEGACY_ABSENT"


@dataclass(frozen=True, slots=True)
class NormativeReferenceSnapshot:
    """Identidade verificável de uma referência usada pela interpretação."""

    instrument_code: str
    instrument_version: str
    provision: str | None
    content_digest: str
    digest_algorithm: str
    source_classification: NormativeSourceClassification

    def __post_init__(self) -> None:
        for field_name in (
            "instrument_code",
            "instrument_version",
            "content_digest",
            "digest_algorithm",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser uma string não vazia.")
        if self.provision is not None and not self.provision.strip():
            raise ValueError("provision, quando informado, não pode ser vazio.")
        if not isinstance(self.source_classification, NormativeSourceClassification):
            raise TypeError("source_classification deve ser NormativeSourceClassification.")

    def canonical_value(self) -> dict[str, str | None]:
        return {
            "instrument_code": self.instrument_code,
            "instrument_version": self.instrument_version,
            "provision": self.provision,
            "content_digest": self.content_digest,
            "digest_algorithm": self.digest_algorithm,
            "source_classification": self.source_classification.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            instrument_code=data["instrument_code"],
            instrument_version=data["instrument_version"],
            provision=data.get("provision"),
            content_digest=data["content_digest"],
            digest_algorithm=data["digest_algorithm"],
            source_classification=NormativeSourceClassification(data["source_classification"]),
        )


@dataclass(frozen=True, slots=True)
class NormativeBasisSnapshot:
    """Base normativa exatamente conhecida e aplicada em um corte temporal."""

    schema_version: int
    normative_basis_id: TypedId
    normative_basis_code: str
    normative_basis_version: int
    policy_id: TypedId
    policy_code: str
    policy_version: int
    rule_versions: tuple[tuple[str, int], ...]
    purpose: str
    jurisdiction: str
    intended_use: str
    reference_time: datetime
    knowledge_cutoff: datetime
    approved_by: str
    approval_authority: str
    approved_at: datetime
    references: tuple[NormativeReferenceSnapshot, ...]
    applicability_conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    snapshot_digest: str = ""

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version < 1
        ):
            raise ValueError("schema_version deve ser um inteiro >= 1.")
        self._require_id(self.normative_basis_id, "normative_basis", "normative_basis_id")
        self._require_id(self.policy_id, "policy", "policy_id")
        for field_name in (
            "normative_basis_code",
            "policy_code",
            "purpose",
            "jurisdiction",
            "intended_use",
            "approved_by",
            "approval_authority",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} deve ser uma string não vazia.")
        for field_name in ("normative_basis_version", "policy_version"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} deve ser um inteiro >= 1.")
        for code, version in self.rule_versions:
            if not code.strip() or isinstance(version, bool) or version < 1:
                raise ValueError("rule_versions exige códigos não vazios e versões >= 1.")
        for field_name in ("reference_time", "knowledge_cutoff", "approved_at"):
            require_utc(getattr(self, field_name), field_name=field_name)
        if self.knowledge_cutoff < self.reference_time:
            raise ValueError("knowledge_cutoff não pode ser anterior a reference_time.")
        if not self.references:
            raise ValueError("NormativeBasisSnapshot exige ao menos uma referência.")
        if not all(isinstance(item, NormativeReferenceSnapshot) for item in self.references):
            raise TypeError("references aceita somente NormativeReferenceSnapshot.")
        for field_name in (
            "applicability_conditions",
            "exceptions",
            "conflicts",
            "gaps",
            "limitations",
        ):
            values = getattr(self, field_name)
            if not isinstance(values, tuple) or any(not item.strip() for item in values):
                raise ValueError(f"{field_name} deve ser uma tupla de textos não vazios.")
        expected_digest = self.compute_digest()
        if self.snapshot_digest and self.snapshot_digest != expected_digest:
            raise ValueError("snapshot_digest não corresponde ao conteúdo normativo.")
        object.__setattr__(self, "snapshot_digest", expected_digest)

    @staticmethod
    def _require_id(value: TypedId, entity_type: str, field_name: str) -> None:
        if not isinstance(value, TypedId):
            raise TypeError(f"{field_name} deve ser TypedId.")
        if value.entity_type != entity_type:
            raise ValueError(f"{field_name} deve ser do tipo {entity_type!r}.")

    def canonical_value(self) -> dict[str, CanonicalValue]:
        """Conteúdo sem o próprio digest, com coleções semanticamente ordenadas."""
        return {
            "schema_version": self.schema_version,
            "normative_basis_id": str(self.normative_basis_id.value),
            "normative_basis_code": self.normative_basis_code,
            "normative_basis_version": self.normative_basis_version,
            "policy_id": str(self.policy_id.value),
            "policy_code": self.policy_code,
            "policy_version": self.policy_version,
            "rule_versions": sorted([code, version] for code, version in self.rule_versions),
            "purpose": self.purpose,
            "jurisdiction": self.jurisdiction,
            "intended_use": self.intended_use,
            "reference_time": self.reference_time,
            "knowledge_cutoff": self.knowledge_cutoff,
            "approved_by": self.approved_by,
            "approval_authority": self.approval_authority,
            "approved_at": self.approved_at,
            "references": [
                item.canonical_value()
                for item in sorted(
                    self.references,
                    key=lambda item: (
                        item.instrument_code,
                        item.instrument_version,
                        item.provision or "",
                        item.content_digest,
                    ),
                )
            ],
            "applicability_conditions": sorted(self.applicability_conditions),
            "exceptions": sorted(self.exceptions),
            "conflicts": sorted(self.conflicts),
            "gaps": sorted(self.gaps),
            "limitations": sorted(self.limitations),
        }

    def compute_digest(self) -> str:
        payload = CanonicalPayload(
            schema="titan.normative_basis_snapshot",
            version=self.schema_version,
            value=self.canonical_value(),
        )
        return hashlib.sha256(payload.canonical_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Representação persistível, com digest já verificado pelo tipo."""
        return {
            "schema_version": self.schema_version,
            "normative_basis_id": str(self.normative_basis_id.value),
            "normative_basis_code": self.normative_basis_code,
            "normative_basis_version": self.normative_basis_version,
            "policy_id": str(self.policy_id.value),
            "policy_code": self.policy_code,
            "policy_version": self.policy_version,
            "rule_versions": [list(item) for item in self.rule_versions],
            "purpose": self.purpose,
            "jurisdiction": self.jurisdiction,
            "intended_use": self.intended_use,
            "reference_time": self.reference_time.isoformat(),
            "knowledge_cutoff": self.knowledge_cutoff.isoformat(),
            "approved_by": self.approved_by,
            "approval_authority": self.approval_authority,
            "approved_at": self.approved_at.isoformat(),
            "references": [item.canonical_value() for item in self.references],
            "applicability_conditions": list(self.applicability_conditions),
            "exceptions": list(self.exceptions),
            "conflicts": list(self.conflicts),
            "gaps": list(self.gaps),
            "limitations": list(self.limitations),
            "snapshot_digest": self.snapshot_digest,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstrói e reconfere o digest; payload adulterado é recusado."""
        return cls(
            schema_version=data["schema_version"],
            normative_basis_id=TypedId.parse("normative_basis", data["normative_basis_id"]),
            normative_basis_code=data["normative_basis_code"],
            normative_basis_version=data["normative_basis_version"],
            policy_id=TypedId.parse("policy", data["policy_id"]),
            policy_code=data["policy_code"],
            policy_version=data["policy_version"],
            rule_versions=tuple((item[0], item[1]) for item in data["rule_versions"]),
            purpose=data["purpose"],
            jurisdiction=data["jurisdiction"],
            intended_use=data["intended_use"],
            reference_time=datetime.fromisoformat(data["reference_time"]),
            knowledge_cutoff=datetime.fromisoformat(data["knowledge_cutoff"]),
            approved_by=data["approved_by"],
            approval_authority=data["approval_authority"],
            approved_at=datetime.fromisoformat(data["approved_at"]),
            references=tuple(
                NormativeReferenceSnapshot.from_dict(item) for item in data["references"]
            ),
            applicability_conditions=tuple(data.get("applicability_conditions", ())),
            exceptions=tuple(data.get("exceptions", ())),
            conflicts=tuple(data.get("conflicts", ())),
            gaps=tuple(data.get("gaps", ())),
            limitations=tuple(data.get("limitations", ())),
            snapshot_digest=data["snapshot_digest"],
        )
