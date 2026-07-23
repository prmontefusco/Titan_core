"""Modelo de domínio imutável para Dossier (Passo 7.5).

Snapshot auditável, imutável e **autocontido** de uma Decision e da Evaluation que
a sustenta. O dossiê deve permitir compreender e verificar a decisão sem depender
de consultas posteriores ao banco: tudo que a explica viaja dentro dele.

O hash usa a serialização canônica `titan-json-v1` já adotada pelo Core, e não um
formato próprio — um dossiê que só o Titan consegue verificar não serve para
verificação externa.
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalSerializer

DOSSIER_DOCUMENT_VERSION = 1

_SERIALIZER = CanonicalSerializer()


def compute_dossier_hash(document: Mapping[str, Any]) -> str:
    """Digest SHA-256 sobre os bytes canônicos do documento.

    Qualquer leitor que possua o documento e a especificação `titan-json-v1`
    recalcula este hash sem acesso ao Titan.
    """
    return hashlib.sha256(_SERIALIZER.serialize(document)).hexdigest()


@dataclass(frozen=True, slots=True)
class Dossier:
    dossier_id: TypedId
    organization_id: OrganizationId
    subject_reference: UniversalReference
    purpose: str
    decision_id: TypedId
    evaluation_id: TypedId
    generated_at: datetime
    document: dict[str, Any]
    dossier_hash: str
    serialization_version: str = CanonicalSerializer.version
    document_version: int = DOSSIER_DOCUMENT_VERSION

    def __post_init__(self) -> None:
        if self.dossier_id.entity_type != "dossier":
            raise ValueError("dossier_id deve ser do tipo 'dossier'.")
        if self.decision_id.entity_type != "decision":
            raise ValueError("decision_id deve ser do tipo 'decision'.")
        if self.evaluation_id.entity_type != "evaluation":
            raise ValueError("evaluation_id deve ser do tipo 'evaluation'.")
        if not isinstance(self.organization_id, OrganizationId):
            raise TypeError("organization_id deve ser OrganizationId.")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            raise ValueError("Todo Dossier exige finalidade (purpose) não vazia.")
        if not isinstance(self.document, dict) or not self.document:
            raise ValueError("Todo Dossier exige documento canônico não vazio.")
        if not isinstance(self.dossier_hash, str) or not self.dossier_hash.strip():
            raise ValueError("dossier_hash deve ser uma string não vazia.")

    def recompute_hash(self) -> str:
        return compute_dossier_hash(self.document)

    def verify(self) -> bool:
        """Verificação offline: o documento confere com o hash que carrega."""
        return self.recompute_hash() == self.dossier_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "dossier_id": str(self.dossier_id.value),
            "organization_id": str(self.organization_id.value),
            "subject_reference": reference_to_dict(self.subject_reference),
            "purpose": self.purpose,
            "decision_id": str(self.decision_id.value),
            "evaluation_id": str(self.evaluation_id.value),
            "generated_at": self.generated_at.isoformat(),
            "serialization_version": self.serialization_version,
            "document_version": self.document_version,
            "dossier_hash": self.dossier_hash,
            "document": self.document,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Dossier":
        subject = reference_from_dict(data["subject_reference"])
        if subject is None:
            raise ValueError("Dossier exige Subject.")
        return cls(
            dossier_id=TypedId(entity_type="dossier", value=UUID(data["dossier_id"])),
            organization_id=OrganizationId(UUID(data["organization_id"])),
            subject_reference=subject,
            purpose=data["purpose"],
            decision_id=TypedId(entity_type="decision", value=UUID(data["decision_id"])),
            evaluation_id=TypedId(entity_type="evaluation", value=UUID(data["evaluation_id"])),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            document=dict(data["document"]),
            dossier_hash=data["dossier_hash"],
            serialization_version=data.get("serialization_version", CanonicalSerializer.version),
            document_version=data.get("document_version", DOSSIER_DOCUMENT_VERSION),
        )
