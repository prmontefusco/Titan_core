"""Modelo de domínio imutável para Dossier (Passo 7.5).

Snapshot auditável, imutável e **autocontido** de uma Decision e da Evaluation que
a sustenta. O dossiê deve permitir compreender e verificar a decisão sem depender
de consultas posteriores ao banco: tudo que a explica viaja dentro dele.

O hash usa a serialização canônica `titan-json-v1` já adotada pelo Core, e não um
formato próprio — um dossiê que só o Titan consegue verificar não serve para
verificação externa.
"""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from packages.core_domain.facts import reference_from_dict, reference_to_dict
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.serialization import CanonicalSerializer

# Versão 2: as entradas de `evidences` passaram a poder carregar o conteúdo da
# evidência (hash, fonte, confiança, revogação) e não apenas o identificador. Os
# campos são aditivos — um leitor da versão 1 continua encontrando o que
# esperava. Dossiês já gravados guardam o próprio documento e a própria versão, e
# seguem verificando contra o hash que carregam.
#
# Versão 3: o documento passou a admitir uma seção de vertical, sob a chave
# `vertical`, isolada e autodescrita. Também aditiva.
DOSSIER_DOCUMENT_VERSION = 3

_SERIALIZER = CanonicalSerializer()

_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class VerticalSection:
    """Conteúdo setorial dentro do dossiê, isolado e autodescrito.

    O Core fornece o envelope e **não interpreta o conteúdo** — não pode, porque
    conhecer vertical lhe é proibido. Ele confere apenas que o namespace é nome
    canônico, que a versão é inteiro positivo e que o conteúdo é um mapa.

    A separação é estrutural, não convenção: tudo da vertical vive sob uma chave
    única, declara de quem é e versiona-se por conta própria. Quem não conhece o
    namespace ignora a seção inteira sem perder nada do que o Core afirma, e a
    vertical evolui seu conteúdo sem mexer na versão do documento do Core.
    """

    namespace: str
    section_version: int
    content: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or not _NAMESPACE_PATTERN.fullmatch(self.namespace):
            raise ValueError("namespace deve ser um nome canônico em minúsculas.")
        if isinstance(self.section_version, bool) or not isinstance(self.section_version, int):
            raise TypeError("section_version deve ser um número inteiro.")
        if self.section_version < 1:
            raise ValueError("section_version deve ser maior ou igual a 1.")
        if not isinstance(self.content, Mapping) or not self.content:
            raise ValueError("A seção de vertical exige conteúdo não vazio.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "section_version": self.section_version,
            "content": dict(self.content),
        }


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
