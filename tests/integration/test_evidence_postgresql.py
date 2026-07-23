"""Testes de integração PostgreSQL com RLS para Evidence e Signature (Passo 5.6)."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.crypto import KeyManagementService
from packages.core_application.evidence_service import EvidenceService
from packages.core_domain.crypto import CryptographicProfile
from packages.core_domain.evidence import (
    ConfidenceLevel,
    ConfidenceTier,
    Source,
    SourceType,
    ValidityPeriod,
    VerificationOutcome,
)
from packages.core_infrastructure.crypto import (
    SoftwareKeyProvider,
    SoftwareSigningProvider,
)
from packages.core_infrastructure.persistence.crypto import TransactionalKeyRegistryRepository
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


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


def test_evidence_postgresql_signing_verification_and_revocation_flow(
    db_connection: Connection,
) -> None:
    org_id = OrganizationId.new()

    # 1. Cadastra a organizacao no banco
    db_connection.execute(
        text(
            """
            INSERT INTO core_identity.organizations (organization_id, record_owner_organization_id)
            VALUES (:id, :id)
            """
        ),
        {"id": org_id.value},
    )

    # 2. Configura RLS para a organizacao
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(org_id.value)},
    )

    key_repo = TransactionalKeyRegistryRepository(connection=db_connection)
    key_service = KeyManagementService(registry=key_repo)

    # Cadastra chave ativa e provedor de assinatura de software
    key_provider = SoftwareKeyProvider()
    k_rec = key_service.register_key(
        organization_id=org_id,
        purpose="Integridade e Assinatura de Evidências",
        public_key_fingerprint="sha256:fingerprint_evidence_key",
    )
    key_provider.register_key(k_rec.key_identifier, b"super_secret_evidence_signing_key_32b")
    signer = SoftwareSigningProvider(key_provider=key_provider)

    evidence_repo = TransactionalEvidenceRepository(connection=db_connection)
    service = EvidenceService(
        repository=evidence_repo,
        signing_provider=signer,
        key_registry=key_repo,
    )

    source = Source(
        source_id=TypedId.new("source"),
        source_type=SourceType.DOCUMENT,
        identifier_uri="https://anvisa.gov.br/licenca/998877",
    )
    author_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    now = datetime.now(UTC)
    vp = ValidityPeriod(
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
    )
    cl = ConfidenceLevel(tier=ConfidenceTier.VERIFIED_SOURCE, reason="Fonte governamental")

    # 3. Registra evidência
    evidence = service.register_evidence(
        organization_id=org_id,
        source=source,
        author_reference=author_ref,
        content=b"Conteudo de teste da licenca sanitaria anvisa",
        confidence_level=cl,
        validity_period=vp,
    )

    # 4. Assina a evidência via serviço
    signed_evidence = service.sign_evidence(
        evidence_id=evidence.evidence_id,
        profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE,
    )
    assert signed_evidence.signature is not None
    assert signed_evidence.signature.profile == CryptographicProfile.INSTITUTIONAL_SIGNATURE
    assert signed_evidence.signature.algorithm == "HMAC-SHA256"

    # 5. Adiciona verificação
    verifier_ref = UniversalReference(
        target_id=TypedId(entity_type="user", value=TypedId.new("user").value),
        organization_id=org_id,
        contract_version=1,
    )
    verified_evidence = service.verify_evidence(
        evidence_id=evidence.evidence_id,
        verifier_reference=verifier_ref,
        outcome=VerificationOutcome.VERIFIED,
        notes="Validação efetuada via consulta ao portal da ANVISA",
    )
    assert len(verified_evidence.verifications) == 1

    # 6. Carrega do banco de dados e verifica se a assinatura foi reidratada perfeitamente
    fetched = service.get_evidence(evidence.evidence_id)
    assert fetched is not None
    assert fetched.signature is not None
    assert fetched.signature.profile == CryptographicProfile.INSTITUTIONAL_SIGNATURE
    assert fetched.signature.algorithm == "HMAC-SHA256"
    assert fetched.signature.key_identifier.key_id == k_rec.key_identifier.key_id
    assert fetched.signature.key_identifier.purpose == "Integridade e Assinatura de Evidências"
