"""Testes de domínio para SourceArtifact e EstablishmentQualificationAssertion (ADR-0045)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.qualification_source_artifact import (
    QualificationSourceArtifact,
    SourceCoverage,
)
from packages.shared_kernel import OrganizationId, TypedId


def _org() -> OrganizationId:
    return OrganizationId(uuid4())


def _establishment_id() -> TypedId:
    return TypedId.new("external_counterparty")


def _artifact(**overrides: Any) -> QualificationSourceArtifact:
    defaults: dict[str, Any] = dict(
        organization_id=_org(),
        source="MAPA",
        source_version="2026-07-27T15:30Z",
        content_hash="sha256:abc",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, 15, 30, tzinfo=UTC),
    )
    defaults.update(overrides)
    return QualificationSourceArtifact.create(**defaults)


def _assertion(**overrides: Any) -> EstablishmentQualificationAssertion:
    artifact = overrides.pop("artifact", None) or _artifact()
    defaults: dict[str, Any] = dict(
        organization_id=artifact.organization_id,
        establishment_id=_establishment_id(),
        qualification_type="EXPORT_CN",
        asserted_status=AssertionStatus.QUALIFIED,
        effective_from=None,
        effective_until=None,
        observed_at=artifact.observed_at,
        source_artifact_id=artifact.artifact_id,
        confidence_tier=ConfidenceTier.VERIFIED_SOURCE,
    )
    defaults.update(overrides)
    return EstablishmentQualificationAssertion.create(**defaults)


class TestQualificationSourceArtifact:
    def test_cria_artefato_valido(self) -> None:
        artifact = _artifact()
        assert artifact.artifact_id.entity_type == "qualification_source_artifact"
        assert artifact.allows_absence_inference()

    def test_partial_nao_autoriza_inferencia_de_ausencia(self) -> None:
        artifact = _artifact(snapshot_semantics=SourceCoverage.PARTIAL)
        assert not artifact.allows_absence_inference()

    def test_unknown_nao_autoriza_inferencia_de_ausencia(self) -> None:
        artifact = _artifact(snapshot_semantics=SourceCoverage.UNKNOWN)
        assert not artifact.allows_absence_inference()

    def test_delta_nao_autoriza_inferencia_de_ausencia(self) -> None:
        artifact = _artifact(snapshot_semantics=SourceCoverage.DELTA)
        assert not artifact.allows_absence_inference()

    def test_source_vazio_e_rejeitado(self) -> None:
        with pytest.raises(ValueError):
            _artifact(source="   ")

    def test_source_version_vazio_e_rejeitado(self) -> None:
        with pytest.raises(ValueError):
            _artifact(source_version="")


class TestEstablishmentQualificationAssertion:
    def test_cria_assertion_valida(self) -> None:
        assertion = _assertion()
        assert assertion.asserted_status == AssertionStatus.QUALIFIED

    def test_source_artifact_id_obrigatorio_com_entity_type_correto(self) -> None:
        """A invariante central da ADR-0045: fato sem proveniência não existe."""
        artifact = _artifact()
        with pytest.raises(ValueError, match="source_artifact_id"):
            EstablishmentQualificationAssertion(
                assertion_id=TypedId.new("establishment_qualification_assertion"),
                organization_id=artifact.organization_id,
                establishment_id=_establishment_id(),
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
                effective_from=None,
                effective_until=None,
                observed_at=artifact.observed_at,
                source_artifact_id=TypedId.new("external_counterparty"),  # tipo errado
                confidence_tier=ConfidenceTier.VERIFIED_SOURCE,
            )

    def test_establishment_id_deve_ser_external_counterparty(self) -> None:
        artifact = _artifact()
        with pytest.raises(ValueError, match="establishment_id"):
            EstablishmentQualificationAssertion(
                assertion_id=TypedId.new("establishment_qualification_assertion"),
                organization_id=artifact.organization_id,
                establishment_id=TypedId.new("animal"),  # tipo errado
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
                effective_from=None,
                effective_until=None,
                observed_at=artifact.observed_at,
                source_artifact_id=artifact.artifact_id,
                confidence_tier=ConfidenceTier.VERIFIED_SOURCE,
            )

    def test_effective_from_posterior_a_until_e_rejeitado(self) -> None:
        base = datetime(2026, 7, 27, tzinfo=UTC)
        with pytest.raises(ValueError, match="effective_from"):
            _assertion(
                effective_from=base,
                effective_until=base - timedelta(days=1),
            )

    def test_known_as_of_reproduz_conhecimento_historico(self) -> None:
        """Reprodução histórica: assertion só é 'conhecida' em cutoff >= recorded_at.

        `recorded_at` é sempre "agora" na criação real (`.create()` não o
        recebe como parâmetro — ver ADR-0045: o Titan nunca fabrica quando
        passou a conhecer algo). O teste fixa esse eixo explicitamente via
        `dataclasses.replace` para exercitar o limite de `known_as_of` sem
        depender do relógio de parede do dia em que a suíte roda.
        """
        observed = datetime(2026, 7, 20, tzinfo=UTC)
        assertion = replace(_assertion(observed_at=observed), recorded_at=observed)

        assert assertion.known_as_of(observed) is True
        assert assertion.known_as_of(observed + timedelta(days=1)) is True
        assert assertion.known_as_of(observed - timedelta(days=1)) is False

    def test_effective_at_sem_datas_declaradas_nao_afirma_cobertura(self) -> None:
        """Sem effective_from/until, a assertion não cobre nenhum instante específico."""
        assertion = _assertion(effective_from=None, effective_until=None)
        assert assertion.effective_at(datetime(2026, 7, 15, tzinfo=UTC)) is False

    def test_effective_at_com_intervalo_declarado(self) -> None:
        assertion = _assertion(
            effective_from=datetime(2026, 3, 1, tzinfo=UTC),
            effective_until=datetime(2026, 7, 10, tzinfo=UTC),
        )
        assert assertion.effective_at(datetime(2026, 5, 1, tzinfo=UTC)) is True
        assert assertion.effective_at(datetime(2026, 7, 15, tzinfo=UTC)) is False
        assert assertion.effective_at(datetime(2026, 1, 1, tzinfo=UTC)) is False

    def test_status_unknown_nao_e_not_qualified(self) -> None:
        """UNKNOWN e NOT_QUALIFIED são estados distintos — nunca confundidos."""
        assertion = _assertion(asserted_status=AssertionStatus.UNKNOWN)
        assert assertion.asserted_status != AssertionStatus.NOT_QUALIFIED
        assert assertion.asserted_status == AssertionStatus.UNKNOWN
