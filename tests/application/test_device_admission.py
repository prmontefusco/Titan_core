"""Testes para Deep Offline Capability e Admissão de Dispositivos (ADR-0021 / Passo 7.9)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from packages.core_application.synchronization_service import (
    DeviceAdmission,
    EvaluatesDeviceTrustAndSession,
    SynchronizationService,
)
from packages.core_domain.events import CanonicalPayload
from packages.core_domain.synchronization import (
    DeviceClockReading,
    DeviceTrustAssessment,
    OfflineCapabilityProfile,
    OfflineOperation,
    OfflineSession,
    TimeConfidenceLevel,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def test_offline_capability_profile() -> None:
    device_id = TypedId.new("device")
    profile = OfflineCapabilityProfile(
        profile_id=TypedId.new("capability_profile"),
        device_id=device_id,
        allowed_operations=("create_fact", "create_event"),
        max_offline_hours=48,
    )

    assert profile.is_operation_allowed("create_fact") is True
    assert profile.is_operation_allowed("CREATE_EVENT") is True
    assert profile.is_operation_allowed("delete_all") is False


def test_offline_session_validity() -> None:
    device_id = TypedId.new("device")
    org_id = OrganizationId(uuid4())
    now = datetime.now(UTC)

    profile = OfflineCapabilityProfile(
        profile_id=TypedId.new("capability_profile"),
        device_id=device_id,
        allowed_operations=("create_fact",),
    )

    session = OfflineSession(
        session_id=TypedId.new("offline_session"),
        device_id=device_id,
        organization_id=org_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=23),
        session_token_hash="a" * 64,
        capability_profile=profile,
    )

    assert session.is_valid_at(now) is True
    assert session.is_valid_at(now + timedelta(hours=24)) is False


def test_device_trust_assessment() -> None:
    device_id = TypedId.new("device")
    now = datetime.now(UTC)

    trusted = DeviceTrustAssessment(
        device_id=device_id,
        trust_score=0.9,
        os_version="Android 14",
        is_jailbroken_or_rooted=False,
        hardware_backed_keystore=True,
        assessed_at=now,
    )
    assert trusted.meets_trust_threshold(0.7) is True

    untrusted = DeviceTrustAssessment(
        device_id=device_id,
        trust_score=0.9,
        os_version="Android 14",
        is_jailbroken_or_rooted=True,
        hardware_backed_keystore=True,
        assessed_at=now,
    )
    assert untrusted.meets_trust_threshold(0.7) is False


def test_evaluates_device_trust_and_session_admissions() -> None:
    device_id = TypedId.new("device")
    org_id = OrganizationId(uuid4())
    device_ref = UniversalReference(target_id=device_id, organization_id=org_id, contract_version=1)
    now = datetime.now(UTC)

    trust_ok = DeviceTrustAssessment(
        device_id=device_id,
        trust_score=0.85,
        os_version="iOS 17.5",
        is_jailbroken_or_rooted=False,
        hardware_backed_keystore=True,
        assessed_at=now,
    )

    profile = OfflineCapabilityProfile(
        profile_id=TypedId.new("capability_profile"),
        device_id=device_id,
        allowed_operations=("create_fact",),
    )

    session_ok = OfflineSession(
        session_id=TypedId.new("offline_session"),
        device_id=device_id,
        organization_id=org_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=10),
        session_token_hash="b" * 64,
        capability_profile=profile,
    )

    evaluator = EvaluatesDeviceTrustAndSession(
        session=session_ok,
        trust_assessment=trust_ok,
        min_trust_score=0.7,
    )

    assert evaluator.admit(org_id, device_ref, now) == DeviceAdmission.PERMITIDO

    trust_bad = DeviceTrustAssessment(
        device_id=device_id,
        trust_score=0.4,
        os_version="iOS 17.5",
        is_jailbroken_or_rooted=False,
        hardware_backed_keystore=False,
        assessed_at=now,
    )
    evaluator_bad_trust = EvaluatesDeviceTrustAndSession(
        session=session_ok,
        trust_assessment=trust_bad,
        min_trust_score=0.7,
    )
    assert evaluator_bad_trust.admit(org_id, device_ref, now) == DeviceAdmission.EM_QUARENTENA


def test_generate_local_preview() -> None:
    org_id = OrganizationId(uuid4())
    device_id = TypedId.new("device")
    now = datetime.now(UTC)

    device_ref = UniversalReference(target_id=device_id, organization_id=org_id, contract_version=1)
    actor_ref = UniversalReference(
        target_id=TypedId.new("user"), organization_id=org_id, contract_version=1
    )

    op = OfflineOperation(
        operation_id=TypedId.new("offline_operation"),
        organization_id=org_id,
        device_reference=device_ref,
        actor_reference=actor_ref,
        semantic_identity="lote.criacao:12345",
        idempotency_key="KEY-LOCAL-PREVIEW-12345",
        operation_type="create_fact",
        contract_version=1,
        local_sequence=1,
        clock=DeviceClockReading(
            client_observed_at=now,
            claimed_occurred_at=now,
            timezone_name="UTC",
            confidence=TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
            last_server_contact_at=now,
        ),
        payload=CanonicalPayload(schema="titan.fact", version=1, value={"k": "v"}),
    )

    service = SynchronizationService(repository=None, effect_handler=None)  # type: ignore
    preview = service.generate_local_preview(op, preview_generated_at=now)

    assert preview.intent_digest == op.intent_digest
    assert preview.predicted_outcome == "ACEITA"
    assert preview.predicted_state_changes["operation_type"] == "create_fact"
