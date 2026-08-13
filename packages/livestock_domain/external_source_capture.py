"""Artefato imutável de material capturado de Source externa (ADR-0058)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class ExternalSourceEnvironment(StrEnum):
    SIMULATED = "SIMULATED"


@dataclass(frozen=True, slots=True)
class ExternalSourceCaptureArtifact:
    artifact_id: TypedId
    organization_id: OrganizationId
    source_profile_code: str
    source_environment: ExternalSourceEnvironment
    contract_version: str
    resource_kind: str
    request_scope_digest: str
    transport_outcome: str
    response_status_code: int | None
    response_digest: str | None
    captured_at: datetime
    parser_name: str
    parser_version: str
    parsing_diagnostic_code: str | None
    recorded_by: TypedId
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.captured_at, field_name="captured_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.artifact_id.entity_type != "external_source_capture_artifact":
            raise ValueError("artifact_id deve ser external_source_capture_artifact.")
        if self.source_environment is not ExternalSourceEnvironment.SIMULATED:
            raise ValueError("O primeiro corte aceita somente ambiente SIMULATED.")
        if self.source_profile_code != "SISBOV_SIMULATOR_LOCAL":
            raise ValueError("O primeiro corte aceita apenas SISBOV_SIMULATOR_LOCAL.")
        for name in (
            "contract_version",
            "resource_kind",
            "transport_outcome",
            "parser_name",
            "parser_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} não pode ser vazio.")
        for name in ("request_scope_digest", "response_digest"):
            digest = getattr(self, name)
            if digest is not None and (
                len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError(f"{name} deve ser SHA-256 hexadecimal.")
        if self.recorded_by.entity_type not in {"actor", "user", "system"}:
            raise ValueError("recorded_by deve apontar para actor, user ou system.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        contract_version: str,
        resource_kind: str,
        request_scope_digest: str,
        transport_outcome: str,
        response_status_code: int | None,
        response_digest: str | None,
        captured_at: datetime,
        parser_name: str,
        parser_version: str,
        parsing_diagnostic_code: str | None,
        recorded_by: TypedId,
    ) -> "ExternalSourceCaptureArtifact":
        return cls(
            artifact_id=TypedId.new("external_source_capture_artifact"),
            organization_id=organization_id,
            source_profile_code="SISBOV_SIMULATOR_LOCAL",
            source_environment=ExternalSourceEnvironment.SIMULATED,
            contract_version=contract_version,
            resource_kind=resource_kind,
            request_scope_digest=request_scope_digest,
            transport_outcome=transport_outcome,
            response_status_code=response_status_code,
            response_digest=response_digest,
            captured_at=captured_at,
            parser_name=parser_name,
            parser_version=parser_version,
            parsing_diagnostic_code=parsing_diagnostic_code,
            recorded_by=recorded_by,
        )
