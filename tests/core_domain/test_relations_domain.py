"""Testes unitários da Relação Universal e Temporal (Passo 7.1)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.core_domain.evidence import ConfidenceLevel, ConfidenceTier
from packages.core_domain.relations import UniversalRelation
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _ref(org_id: OrganizationId | None, entity_type: str = "subject") -> UniversalReference:
    return UniversalReference(
        target_id=TypedId.new(entity_type), organization_id=org_id, contract_version=1
    )


def _confidence() -> ConfidenceLevel:
    return ConfidenceLevel(tier=ConfidenceTier.INFORMED, reason="Declarado pelo operador.")


def _relation(
    org_id: OrganizationId,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    **overrides: object,
) -> UniversalRelation:
    kwargs: dict[str, object] = {
        "organization_id": org_id,
        "source_reference": _ref(org_id),
        "target_reference": _ref(org_id),
        "relation_type": "composicao",
        "created_at": datetime.now(UTC),
        "confidence": _confidence(),
        "valid_from": valid_from,
        "valid_until": valid_until,
    }
    kwargs.update(overrides)
    return UniversalRelation.create(**kwargs)  # type: ignore[arg-type]


def test_relation_type_must_be_canonical() -> None:
    org_id = OrganizationId.new()
    with pytest.raises(ValueError, match="nome canônico"):
        _relation(org_id, relation_type="Composição Física")


def test_relation_rejects_reference_from_another_organization() -> None:
    org_id = OrganizationId.new()
    outra_org = OrganizationId.new()

    with pytest.raises(ValueError, match="não concede acesso entre Organizations"):
        _relation(org_id, target_reference=_ref(outra_org))

    with pytest.raises(ValueError, match="não concede acesso entre Organizations"):
        _relation(org_id, source_reference=_ref(outra_org))


def test_relation_rejects_self_link() -> None:
    org_id = OrganizationId.new()
    mesma = _ref(org_id)
    with pytest.raises(ValueError, match="ele mesmo"):
        _relation(org_id, source_reference=mesma, target_reference=mesma)


def test_quantity_requires_unit_and_rejects_float() -> None:
    org_id = OrganizationId.new()

    with pytest.raises(ValueError, match="exige unidade"):
        _relation(org_id, quantity=Decimal("10.5"))

    with pytest.raises(TypeError, match="não aceita float"):
        _relation(org_id, quantity=10.5, unit="kg")

    with pytest.raises(ValueError, match="não pode ser negativa"):
        _relation(org_id, quantity=Decimal("-1"), unit="kg")

    valida = _relation(org_id, quantity=Decimal("10.5"), unit="kg")
    assert valida.quantity == Decimal("10.5")


def test_relation_temporal_window() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    relation = _relation(org_id, valid_from=t0, valid_until=t0 + timedelta(days=10))

    assert not relation.is_valid_at(t0 - timedelta(days=1))
    assert relation.is_valid_at(t0)
    assert relation.is_valid_at(t0 + timedelta(days=5))
    assert not relation.is_valid_at(t0 + timedelta(days=11))


def test_open_ended_relation_is_valid_from_and_until_forever() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    aberta = _relation(org_id)

    assert aberta.is_valid_at(t0 - timedelta(days=365))
    assert aberta.is_valid_at(t0 + timedelta(days=365))


def test_close_preserves_history_instead_of_deleting() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    aberta = _relation(org_id, valid_from=t0)

    encerrada = aberta.close(t0 + timedelta(days=30))

    # O vínculo não some: passa a ter fim e segue respondendo o passado.
    assert encerrada.relation_id == aberta.relation_id
    assert encerrada.is_valid_at(t0 + timedelta(days=10))
    assert not encerrada.is_valid_at(t0 + timedelta(days=31))

    with pytest.raises(ValueError, match="já possui fim de vigência"):
        encerrada.close(t0 + timedelta(days=40))

    with pytest.raises(ValueError, match="anterior ao início"):
        aberta.close(t0 - timedelta(days=1))


def test_relation_roundtrips_through_dict() -> None:
    org_id = OrganizationId.new()
    t0 = datetime.now(UTC)
    original = _relation(
        org_id,
        valid_from=t0,
        valid_until=t0 + timedelta(days=5),
        quantity=Decimal("42.750"),
        unit="kg",
        created_by_event=TypedId.new("domain_event"),
        evidence_references=(_ref(org_id, "evidence"),),
        metadata={"origem": "importacao"},
        metadata_version=2,
    )
    restaurada = UniversalRelation.from_dict(original.to_dict())

    assert restaurada == original
    assert restaurada.quantity == Decimal("42.750")


def test_relation_is_immutable() -> None:
    relation = _relation(OrganizationId.new())
    with pytest.raises(AttributeError):
        relation.relation_type = "outra"  # type: ignore[misc]
