"""Testes para o serviço de importação de qualificações."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.livestock_application.establishment_qualification_import_service import (
    EstablishmentQualificationImportService,
    QualificationImportInput,
)
from packages.livestock_domain.establishment_qualification import (
    EstablishmentQualificationStatus,
)
from packages.shared_kernel import OrganizationId, TypedId


class MockQualificationRepository:
    """Repository mock para testes."""

    def __init__(self):
        self.store: dict[str, dict] = {}

    def save(self, qualification):
        key = (
            str(qualification.organization_id.value),
            str(qualification.source_version),
            str(qualification.counterparty_id.value),
            qualification.market_purpose,
        )
        self.store[key] = qualification

    def find_by_source_version(self, organization_id, source_version):
        return [
            qual
            for qual in self.store.values()
            if str(qual.organization_id.value) == str(organization_id.value)
            and qual.source_version == source_version
        ]

    def find_active_by_organization(self, organization_id):
        return [
            qual
            for qual in self.store.values()
            if str(qual.organization_id.value) == str(organization_id.value)
            and qual.status == EstablishmentQualificationStatus.HABILITADO
        ]


class TestEstablishmentQualificationImportService:
    """Testes da importacao e reconciliacao."""

    @pytest.fixture
    def service(self):
        repo = MockQualificationRepository()
        return EstablishmentQualificationImportService(repository=repo)

    @pytest.fixture
    def org_id(self):
        return OrganizationId(uuid4())

    @pytest.fixture
    def counterparty_id(self):
        return TypedId(entity_type="external_counterparty", value=uuid4())

    def test_importacao_basica_cria_qualificacoes(self, service, org_id, counterparty_id):
        """Teste 1: Importar lista basica de qualificacoes."""
        entrada = [
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="exportacao-china",
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="exportacao-usa",
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
        ]

        resultado = service.import_qualifications(
            organization_id=org_id,
            qualifications=entrada,
            source_version="2026-07-27T00:00Z",
        )

        assert resultado.success
        assert resultado.imported == 2
        assert resultado.revoked == 0
        assert resultado.unchanged == 0
        assert resultado.rejected == 0

    def test_idempotencia_reimportacao_nao_duplica(self, service, org_id, counterparty_id):
        """Teste 3: Reimportar mesma versao nao duplica."""
        entrada = [
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="exportacao-china",
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
        ]

        versao = "2026-07-27T00:00Z"

        # Primeira importacao
        resultado1 = service.import_qualifications(
            organization_id=org_id,
            qualifications=entrada,
            source_version=versao,
        )
        assert resultado1.imported == 1

        # Reimportacao da mesma versao
        resultado2 = service.import_qualifications(
            organization_id=org_id,
            qualifications=entrada,
            source_version=versao,
        )
        assert resultado2.imported == 0
        assert resultado2.unchanged == 1

    def test_validacao_rejeita_entrada_invalida(self, service, org_id, counterparty_id):
        """Teste: Entrada com market_purpose vazio eh rejeitada."""
        entrada = [
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="",  # INVALIDO
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
        ]

        resultado = service.import_qualifications(
            organization_id=org_id,
            qualifications=entrada,
            source_version="2026-07-27T00:00Z",
        )

        assert not resultado.success
        assert resultado.rejected == 1
        assert len(resultado.errors) > 0

    def test_data_hash_eh_determinista(self, service, counterparty_id):
        """Teste: Mesmo conteudo produz mesmo hash."""
        entrada1 = [
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="exportacao-china",
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
        ]

        entrada2 = [
            QualificationImportInput(
                counterparty_id=counterparty_id,
                market_purpose="exportacao-china",
                status=EstablishmentQualificationStatus.HABILITADO,
                source_name="FRIGORICO",
            ),
        ]

        hash1 = EstablishmentQualificationImportService.compute_data_hash(entrada1)
        hash2 = EstablishmentQualificationImportService.compute_data_hash(entrada2)

        assert hash1 == hash2
        assert hash1.startswith("sha256:")
        assert len(hash1) == 71  # "sha256:" + 64 hex characters
