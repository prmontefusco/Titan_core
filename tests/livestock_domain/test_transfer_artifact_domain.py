from datetime import UTC, datetime, timedelta

from packages.livestock_domain.transfer_artifact import (
    HistoryCoverage,
    TransferArtifactGapCode,
)


def test_cobertura_antes_da_transferencia_declara_lacuna() -> None:
    transferencia = datetime.now(UTC)
    conhecido_ate = transferencia - timedelta(hours=12)

    coverage = HistoryCoverage.from_transfer(
        known_from=transferencia - timedelta(days=300),
        known_until=conhecido_ate,
        transfer_effective_at=transferencia,
    )

    assert coverage.gaps[0].code is TransferArtifactGapCode.COVERAGE_BEFORE_TRANSFER
    assert coverage.gaps[0].starts_at == conhecido_ate
    assert coverage.gaps[0].ends_at == transferencia


def test_ausencia_de_cobertura_nao_vira_historico_vazio() -> None:
    transferencia = datetime.now(UTC)

    coverage = HistoryCoverage.from_transfer(
        known_from=None,
        known_until=None,
        transfer_effective_at=transferencia,
    )

    assert coverage.gaps[0].code is TransferArtifactGapCode.HISTORY_BEFORE_ACQUISITION_UNKNOWN
