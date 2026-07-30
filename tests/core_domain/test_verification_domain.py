"""Testes de domínio para SignatureTarget e SignaturePurpose (ADR-0055 §8)."""

import pytest

from packages.core_domain.verification import SignaturePurpose, SignatureTarget


def _target(**overrides: object) -> SignatureTarget:
    base: dict[str, object] = {
        "target_type": "bundle_manifest",
        "target_identifier": "a" * 64,
        "domain": "titan.verification_bundle",
        "contract_version": 1,
        "purpose": SignaturePurpose.EMISSAO,
    }
    base.update(overrides)
    return SignatureTarget(**base)  # type: ignore[arg-type]


def test_valid_signature_target_is_constructed() -> None:
    alvo = _target()
    assert alvo.target_type == "bundle_manifest"
    assert alvo.purpose is SignaturePurpose.EMISSAO


def test_empty_target_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_type"):
        _target(target_type="")


def test_empty_target_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_identifier"):
        _target(target_identifier="")


def test_empty_domain_is_rejected() -> None:
    with pytest.raises(ValueError, match="domain"):
        _target(domain="")


def test_contract_version_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="contract_version"):
        _target(contract_version=0)


def test_contract_version_must_be_an_int_not_a_bool() -> None:
    with pytest.raises(TypeError, match="contract_version"):
        _target(contract_version=True)


def test_purpose_must_be_a_signature_purpose() -> None:
    with pytest.raises(TypeError, match="purpose"):
        _target(purpose="EMISSAO")


def test_distinct_purposes_are_not_interchangeable() -> None:
    """ADR-0055 §8: assinaturas de emissão, revisão, aprovação, selo temporal e
    preservação têm escopos distintos -- o vocabulário precisa distingui-las."""
    assert {p.value for p in SignaturePurpose} == {
        "EMISSAO",
        "REVISAO",
        "APROVACAO",
        "SELO_TEMPORAL",
        "PRESERVACAO",
    }
