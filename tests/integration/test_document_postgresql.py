"""Testes de integração PostgreSQL com RLS para a gestão de Documentos e Anexos (Passo 5.7)."""

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.document_service import DocumentService
from packages.core_infrastructure.persistence.evidence import TransactionalAttachmentRepository
from packages.core_infrastructure.storage import SoftwareBlobStorage
from packages.shared_kernel import OrganizationId


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        with conn.begin():
            yield conn


def test_document_service_upload_download_hash_validation_and_rls(
    db_connection: Connection,
) -> None:
    org_id_1 = OrganizationId.new()
    org_id_2 = OrganizationId.new()

    # 1. Cadastra as organizacoes
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES
                (:id1, :id1),
                (:id2, :id2)
            """
        ),
        {
            "id1": org_id_1.value,
            "id2": org_id_2.value,
        },
    )

    storage = SoftwareBlobStorage()

    # 2. Upload para org_1 sob RLS
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_1.value)},
    )

    repo_1 = TransactionalAttachmentRepository(connection=db_connection)
    service_1 = DocumentService(storage=storage, repository=repo_1)

    original_content = b"Conteudo integro do laudo veterinario expedido em 2026"
    attachment_1 = service_1.upload_attachment(
        organization_id=org_id_1,
        filename="laudo_vet_2026.pdf",
        content_type="application/pdf",
        content=original_content,
    )

    assert attachment_1.filename == "laudo_vet_2026.pdf"
    assert attachment_1.size_bytes == len(original_content)

    # Download e verificacao de hash de integridade
    att_fetched, content_fetched = service_1.download_attachment(attachment_1.attachment_id)
    assert att_fetched.attachment_id == attachment_1.attachment_id
    assert content_fetched == original_content

    # 3. Adulteração do binário no storage -> deve falhar com ValueError na validação de hash
    storage._storage[attachment_1.blob_uri] = b"Conteudo adulterado ilicitamente"
    with pytest.raises(ValueError, match="Integridade do arquivo comprometida"):
        service_1.download_attachment(attachment_1.attachment_id)

    # Restaura binario integro para os demais testes
    storage._storage[attachment_1.blob_uri] = original_content

    # 4. Isolamento de tenant via RLS (org_2 nao enxerga o anexo da org_1)
    # O usuario titan e superusuario e ignora RLS; a checagem exige um role sem BYPASSRLS.
    role_name = f"titan_test_rls_{uuid4().hex}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    db_connection.execute(text(f"GRANT SELECT ON core_audit.attachments TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id_2.value)},
    )

    repo_2 = TransactionalAttachmentRepository(connection=db_connection)
    service_2 = DocumentService(storage=storage, repository=repo_2)

    unseen_att = service_2.get_attachment(attachment_1.attachment_id)
    assert unseen_att is None

    with pytest.raises(KeyError, match="não encontrado"):
        service_2.download_attachment(attachment_1.attachment_id)

    db_connection.execute(text("RESET ROLE"))
    db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
    db_connection.execute(text(f"DROP ROLE {quoted_role}"))
