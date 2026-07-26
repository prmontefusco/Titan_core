from datetime import UTC, datetime

import pytest

from packages.livestock_domain.external_counterparty import CounterpartyType, ExternalCounterparty
from packages.shared_kernel import OrganizationId, TypedId


def test_contraparte_externa_e_representacao_local() -> None:
    contraparte = ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=OrganizationId.new(),
        name="Frigorifico Central",
        counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
        identifiers=("CNPJ:00000000000100", "SIF:1234"),
        created_at=datetime.now(UTC),
    )

    assert contraparte.counterparty_type is CounterpartyType.SLAUGHTERHOUSE
    assert "CNPJ:00000000000100" in contraparte.identifiers


def test_contraparte_externa_recusa_identificador_vazio() -> None:
    with pytest.raises(ValueError, match="identifiers"):
        ExternalCounterparty(
            counterparty_id=TypedId.new("external_counterparty"),
            organization_id=OrganizationId.new(),
            name="Fazenda Destino",
            counterparty_type=CounterpartyType.FARM,
            identifiers=(" ",),
        )
