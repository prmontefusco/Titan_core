"""Caso de uso e portas de gestão de Documentos e Anexos (ADR-0038/Passo 5.7)."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from packages.core_domain.evidence import Attachment
from packages.shared_kernel import OrganizationId, TypedId


class BlobStoragePort(Protocol):
    def upload_blob(self, container_name: str, blob_name: str, content: bytes) -> str: ...

    def download_blob(self, blob_uri: str) -> bytes | None: ...


class AttachmentRepositoryPort(Protocol):
    def save(self, attachment: Attachment) -> None: ...

    def get_by_id(self, attachment_id: TypedId) -> Attachment | None: ...

    def list_by_organization(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Attachment]: ...


@dataclass(frozen=True, slots=True)
class DocumentService:
    storage: BlobStoragePort
    repository: AttachmentRepositoryPort

    def upload_attachment(
        self,
        organization_id: OrganizationId,
        filename: str,
        content_type: str,
        content: bytes,
        container_name: str = "attachments",
    ) -> Attachment:
        if not isinstance(content, bytes) or not content:
            raise ValueError("O conteúdo do arquivo deve ser bytes não vazio.")

        content_hash = hashlib.sha256(content).digest()
        attachment_id = TypedId.new("attachment")
        blob_name = f"{organization_id.value}/{attachment_id.value}/{filename}"

        blob_uri = self.storage.upload_blob(container_name, blob_name, content)

        attachment = Attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            content_hash=content_hash,
            blob_uri=blob_uri,
            uploaded_at=datetime.now(UTC),
        )

        self.repository.save(attachment)
        return attachment

    def download_attachment(self, attachment_id: TypedId) -> tuple[Attachment, bytes]:
        attachment = self.repository.get_by_id(attachment_id)
        if attachment is None:
            raise KeyError(f"Anexo {attachment_id.value} não encontrado.")

        content = self.storage.download_blob(attachment.blob_uri)
        if content is None:
            raise FileNotFoundError(
                f"Objeto do anexo não encontrado no storage: {attachment.blob_uri}"
            )

        computed_hash = hashlib.sha256(content).digest()
        if computed_hash != attachment.content_hash:
            raise ValueError(
                "Integridade do arquivo comprometida: o hash do conteúdo diverge do registrado."
            )

        return attachment, content

    def get_attachment(self, attachment_id: TypedId) -> Attachment | None:
        return self.repository.get_by_id(attachment_id)

    def list_attachments(
        self, organization_id: OrganizationId, limit: int = 50, offset: int = 0
    ) -> list[Attachment]:
        return self.repository.list_by_organization(
            organization_id=organization_id, limit=limit, offset=offset
        )
