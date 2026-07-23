"""Adapter de armazenamento de objetos (Blob Storage) em memória (ADR-0038/Passo 5.7)."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class SoftwareBlobStorage:
    """Provedor in-memory de Blob Storage agnóstico para desenvolvimento e testes."""

    _storage: dict[str, bytes] = field(default_factory=dict)

    def upload_blob(self, container_name: str, blob_name: str, content: bytes) -> str:
        if not isinstance(content, bytes):
            raise TypeError("O conteúdo do blob deve ser bytes.")

        blob_uri = f"blob://{container_name}/{blob_name}"
        self._storage[blob_uri] = content
        return blob_uri

    def download_blob(self, blob_uri: str) -> bytes | None:
        return self._storage.get(blob_uri)
