"""Add Ed25519 signatures to event integrity links.

Revision ID: 20260909_0084
Revises: 20260909_0083
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0084"
down_revision: str | None = "20260909_0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "core_audit"
TABLE = "domain_event_integrity"


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("signature_algorithm", sa.String(length=30), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE, sa.Column("signature_profile", sa.String(length=100), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE, sa.Column("signature_profile_version", sa.Integer(), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE, sa.Column("signature_key_id", sa.String(length=100), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE, sa.Column("signature_public_key", sa.LargeBinary(), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE, sa.Column("signature_bytes", sa.LargeBinary(), nullable=True), schema=SCHEMA
    )
    op.add_column(
        TABLE,
        sa.Column("signature_signed_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_integrity_signature_public_key_size",
        TABLE,
        "signature_public_key IS NULL OR octet_length(signature_public_key) = 32",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_integrity_signature_bytes_size",
        TABLE,
        "signature_bytes IS NULL OR octet_length(signature_bytes) = 64",
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint("ck_integrity_signature_bytes_size", TABLE, schema=SCHEMA)
    op.drop_constraint("ck_integrity_signature_public_key_size", TABLE, schema=SCHEMA)
    for column in (
        "signature_signed_at",
        "signature_bytes",
        "signature_public_key",
        "signature_key_id",
        "signature_profile_version",
        "signature_profile",
        "signature_algorithm",
    ):
        op.drop_column(TABLE, column, schema=SCHEMA)
