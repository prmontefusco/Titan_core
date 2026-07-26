from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_domain.imported_fact import FactOrigin, ImportedLivestockFact
from packages.shared_kernel import OrganizationId, TypedId


def test_fato_importado_preserva_origem_e_autoria_externa() -> None:
    fact = ImportedLivestockFact.create(
        organization_id=OrganizationId.new(),
        animal_id=TypedId.new("animal"),
        source_artifact_id=TypedId.new("received_transfer_artifact"),
        fact_type="livestock.treatment_applied",
        occurred_at=datetime.now(UTC),
        asserted_by="Fazenda Origem",
        received_by=TypedId.new("actor"),
        confidence_tier=ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED,
        payload={"medication": "Vacina ficticia"},
    )

    assert fact.origin is FactOrigin.IMPORTED_ASSERTION
    assert fact.asserted_by == "Fazenda Origem"
    assert fact.confidence_tier is ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED


def test_fato_importado_nao_pode_virar_declaracao_local() -> None:
    with pytest.raises(ValueError, match="IMPORTED_ASSERTION"):
        ImportedLivestockFact(
            imported_fact_id=TypedId.new("imported_livestock_fact"),
            organization_id=OrganizationId.new(),
            animal_id=TypedId.new("animal"),
            source_artifact_id=TypedId.new("received_transfer_artifact"),
            fact_type="livestock.treatment_applied",
            occurred_at=datetime.now(UTC),
            asserted_by="Fazenda Origem",
            received_by=TypedId.new("actor"),
            confidence_tier=ConfidenceTier.DOCUMENTED,
            payload=MappingProxyType({}),
            origin=FactOrigin.LOCAL_DECLARATION,
        )
