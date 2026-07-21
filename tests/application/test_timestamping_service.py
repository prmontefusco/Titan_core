import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.core_application import (
    TemporalAnchor,
    TimestampAttempt,
    TimestampAttemptStatus,
    TimestampProviderUnavailable,
    TimestampService,
    TimestampValidation,
    TimestampValidationStatus,
)
from packages.core_infrastructure.fake_timestamp import (
    FakeTimestampProfile,
    FakeTimestampProvider,
    FakeTimestampTokenValidator,
)
from packages.core_integrity import (
    IntegrityCheckpoint,
    build_event_chain_entry,
    build_integrity_checkpoint,
)
from packages.shared_kernel import FixedClock, TypedId
from tests.core_domain.test_domain_event import reference, valid_event

NOW = datetime(2026, 7, 21, 20, 0, tzinfo=UTC)
SECRET = b"titan-fake-timestamp-secret-32-bytes-minimum"


@dataclass
class InMemoryTimestampWriter:
    attempts: list[TimestampAttempt] = field(default_factory=list)
    validations: list[TimestampValidation] = field(default_factory=list)
    anchors: list[TemporalAnchor] = field(default_factory=list)

    def add_attempt(self, attempt: TimestampAttempt) -> None:
        self.attempts.append(attempt)

    def add_validation(self, validation: TimestampValidation) -> None:
        self.validations.append(validation)

    def add_anchor(self, anchor: TemporalAnchor) -> None:
        self.anchors.append(anchor)


def _profile(
    *,
    policy: str = "DESENVOLVIMENTO_SEM_CONFIANCA_JURIDICA",
    trust_chain: tuple[str, ...] = ("RAIZ_FALSA_LOCAL", "AUTORIDADE_FALSA_LOCAL"),
) -> FakeTimestampProfile:
    return FakeTimestampProfile(
        provider_id="FAKE_TSA_LOCAL",
        policy=policy,
        authority_id="AUTORIDADE_FALSA_LOCAL",
        trust_chain=trust_chain,
        secret=SECRET,
        token_lifetime=timedelta(minutes=5),
    )


def _checkpoint() -> IntegrityCheckpoint:
    event = replace(valid_event(), aggregate_version=1)
    entry = build_event_chain_entry(event, None)
    return build_integrity_checkpoint(
        checkpoint_id=TypedId.new("integrity_checkpoint"),
        entries=(entry,),
        observed_at=NOW - timedelta(minutes=1),
        producer_reference=reference("service_identity", event.organization_id),
        correlation_id=TypedId.new("correlation"),
        causation_id=event.event_id,
    )


def _request(
    service: TimestampService, provider: FakeTimestampProvider
) -> tuple[IntegrityCheckpoint, TimestampAttempt]:
    checkpoint = _checkpoint()
    attempt = service.request(
        checkpoint=checkpoint,
        attempt_id=TypedId.new("timestamp_attempt"),
        policy=_profile().policy,
        nonce=b"0123456789abcdef",
        correlation_id=TypedId.new("correlation"),
        requested_at=NOW,
        provider=provider,
    )
    return checkpoint, attempt


def test_fake_token_is_validated_and_only_then_creates_anchor() -> None:
    writer = InMemoryTimestampWriter()
    service = TimestampService(writer)
    profile = _profile()
    checkpoint, attempt = _request(service, FakeTimestampProvider(profile, FixedClock(NOW)))

    validation, anchor = service.validate_and_anchor(
        checkpoint=checkpoint,
        attempt=attempt,
        validation_id=TypedId.new("timestamp_validation"),
        anchor_id=TypedId.new("temporal_anchor"),
        validated_at=NOW + timedelta(minutes=1),
        validator=FakeTimestampTokenValidator(profile),
    )

    assert validation.status is TimestampValidationStatus.VALIDO
    assert validation.proved_at == NOW
    assert anchor is not None
    assert anchor.message_imprint == checkpoint.checkpoint_digest
    assert writer.anchors == [anchor]


def test_unavailable_provider_keeps_checkpoint_pending_and_retry_uses_same_imprint() -> None:
    writer = InMemoryTimestampWriter()
    service = TimestampService(writer)
    profile = _profile()
    checkpoint, pending = _request(
        service, FakeTimestampProvider(profile, FixedClock(NOW), available=False)
    )

    completed = service.request(
        checkpoint=checkpoint,
        attempt_id=TypedId.new("timestamp_attempt"),
        policy=profile.policy,
        nonce=b"fedcba9876543210",
        correlation_id=TypedId.new("correlation"),
        requested_at=NOW + timedelta(minutes=1),
        provider=FakeTimestampProvider(profile, FixedClock(NOW + timedelta(minutes=1))),
    )

    assert pending.status is TimestampAttemptStatus.PENDENTE
    assert completed.status is TimestampAttemptStatus.TOKEN_RECEBIDO
    assert pending.request.attempt_id != completed.request.attempt_id
    assert pending.request.message_imprint == completed.request.message_imprint


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("signature", "ASSINATURA_INVALIDA"),
        ("imprint", "IMPRINT_DIVERGENTE"),
        ("policy", "POLITICA_DIVERGENTE"),
        ("chain", "CADEIA_DIVERGENTE"),
        ("validity", "VALIDADE_INVALIDA"),
    ],
)
def test_rejects_invalid_fake_token_dimensions(mutation: str, reason: str) -> None:
    writer = InMemoryTimestampWriter()
    service = TimestampService(writer)
    expected_profile = _profile()
    checkpoint, attempt = _request(
        service, FakeTimestampProvider(expected_profile, FixedClock(NOW))
    )
    validated_at = NOW + timedelta(minutes=1)

    if mutation == "signature":
        assert attempt.raw_token is not None
        token = json.loads(attempt.raw_token)
        signature = token["signature"]
        token["signature"] = ("0" if signature[0] != "0" else "1") + signature[1:]
        attempt = replace(
            attempt,
            raw_token=json.dumps(token, sort_keys=True, separators=(",", ":")).encode(),
        )
    elif mutation == "imprint":
        wrong_request = replace(attempt.request, message_imprint=b"\x01" * 32)
        response = FakeTimestampProvider(expected_profile, FixedClock(NOW)).issue(wrong_request)
        attempt = replace(attempt, raw_token=response.raw_token)
    elif mutation == "policy":
        issuing_profile = _profile(policy="OUTRA_POLITICA")
        response = FakeTimestampProvider(issuing_profile, FixedClock(NOW)).issue(
            replace(attempt.request, policy="OUTRA_POLITICA")
        )
        attempt = replace(attempt, raw_token=response.raw_token)
    elif mutation == "chain":
        issuing_profile = _profile(trust_chain=("OUTRA_RAIZ", "AUTORIDADE_FALSA_LOCAL"))
        response = FakeTimestampProvider(issuing_profile, FixedClock(NOW)).issue(attempt.request)
        attempt = replace(attempt, raw_token=response.raw_token)
    else:
        validated_at = NOW + timedelta(minutes=6)

    validation, anchor = service.validate_and_anchor(
        checkpoint=checkpoint,
        attempt=attempt,
        validation_id=TypedId.new("timestamp_validation"),
        anchor_id=TypedId.new("temporal_anchor"),
        validated_at=validated_at,
        validator=FakeTimestampTokenValidator(expected_profile),
    )

    assert validation.status is TimestampValidationStatus.INVALIDO
    assert validation.reason_code == reason
    assert anchor is None


def test_provider_unavailable_is_a_specific_operational_condition() -> None:
    provider = FakeTimestampProvider(_profile(), FixedClock(NOW), available=False)
    service = TimestampService(InMemoryTimestampWriter())
    _, attempt = _request(service, provider)

    assert attempt.status is TimestampAttemptStatus.PENDENTE
    with pytest.raises(TimestampProviderUnavailable):
        provider.issue(attempt.request)


def test_attempt_from_another_checkpoint_cannot_create_anchor() -> None:
    writer = InMemoryTimestampWriter()
    service = TimestampService(writer)
    checkpoint, attempt = _request(service, FakeTimestampProvider(_profile(), FixedClock(NOW)))
    other_checkpoint = replace(checkpoint, checkpoint_id=TypedId.new("integrity_checkpoint"))

    with pytest.raises(ValueError, match="CHECKPOINT_DIVERGENTE"):
        service.validate_and_anchor(
            checkpoint=other_checkpoint,
            attempt=attempt,
            validation_id=TypedId.new("timestamp_validation"),
            anchor_id=TypedId.new("temporal_anchor"),
            validated_at=NOW,
            validator=FakeTimestampTokenValidator(_profile()),
        )
