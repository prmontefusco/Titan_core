from pathlib import Path

from packages.core_infrastructure.persistence.outbox import (
    outbox_messages_table,
    outbox_publication_attempts_table,
    outbox_publication_state_table,
)


def test_outbox_is_protected_and_preserves_versioned_envelope() -> None:
    assert "PROTECTED" in str(outbox_messages_table.comment)


def test_outbox_publication_state_is_operational_and_protected() -> None:
    assert "PROTECTED" in str(outbox_publication_state_table.comment)
    assert "PROTECTED" in str(outbox_publication_attempts_table.comment)

    for column in (
        "message_id",
        "record_owner_organization_id",
        "status",
        "claim_token",
        "publisher_id",
        "lease_expires_at",
        "attempt_count",
    ):
        assert column in outbox_publication_state_table.c

    for column in (
        "attempt_id",
        "message_id",
        "record_owner_organization_id",
        "claim_token",
        "publisher_id",
        "result",
        "attempted_at",
    ):
        assert column in outbox_publication_attempts_table.c
    for column in (
        "message_id",
        "record_owner_organization_id",
        "kind",
        "contract_type",
        "contract_version",
        "causation_id",
        "payload_canonical_bytes",
        "classification",
        "status",
    ):
        assert column in outbox_messages_table.c


def test_outbox_migration_has_no_update_or_delete_policy() -> None:
    source = Path(
        "packages/core_infrastructure/persistence/migrations/versions/"
        "20260722_0013_create_outbox_messages.py"
    ).read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0013"' in source
    assert 'down_revision: str | None = "20260722_0012"' in source
    assert "FOR UPDATE" not in source
    assert "FOR DELETE" not in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "fk_outbox_causation_event_owner" in source


def test_outbox_publication_migration_has_recoverable_claims() -> None:
    source = (
        Path("packages/core_infrastructure/persistence/migrations/versions")
        / "20260722_0014_create_outbox_publication_state.py"
    ).read_text(encoding="utf-8")

    assert "lease_expires_at" in source
    assert "RESULTADO_DESCONHECIDO" in source
    assert "ACEITA_PELO_BROKER" in source
    assert "REJEITADA_PELO_BROKER" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
