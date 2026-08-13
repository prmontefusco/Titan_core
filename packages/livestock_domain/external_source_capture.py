"""Artefato imutável de material capturado de Source externa (ADR-0058)."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class ExternalSourceEnvironment(StrEnum):
    SIMULATED = "SIMULATED"


class ExternalSourceCaptureAssociationReviewStatus(StrEnum):
    CONFIRMED_CANDIDATE = "CONFIRMED_CANDIDATE"
    REJECTED = "REJECTED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"


_REVIEW_PROJECTION_FIELDS: dict[str, frozenset[str]] = {
    "ANIMAL": frozenset({"statusAnimal", "ERASPropriedadeLocalizacao"}),
    "GTA": frozenset(
        {
            "status",
            "dataEmissao",
            "ERASPropriedadeOrigem",
            "ERASPropriedadeDestino",
        }
    ),
    "MOVEMENT": frozenset({"statusMovimentacao", "gtas", "animais"}),
}


def _freeze_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("review_projection possui chave n\u00e3o textual.")
        return MappingProxyType({key: _freeze_projection(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_projection(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError("review_projection possui valor n\u00e3o serializ\u00e1vel.")


def _thaw_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_projection(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_projection(item) for item in value]
    return value


def _canonical_projection_digest(projection: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _thaw_projection(projection),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(canonical.encode()).hexdigest()


def _validated_review_projection(
    projection: Mapping[str, Any], *, resource_kind: str
) -> MappingProxyType[str, Any]:
    frozen = _freeze_projection(projection)
    if not isinstance(frozen, MappingProxyType):
        raise TypeError("review_projection deve ser objeto.")
    if set(frozen) != {"resource_kind", "external_reference", "declared_fields"}:
        raise ValueError("review_projection possui campos n\u00e3o permitidos.")
    if frozen["resource_kind"] != resource_kind or resource_kind not in _REVIEW_PROJECTION_FIELDS:
        raise ValueError("review_projection deve corresponder ao resource_kind da captura.")
    if (
        not isinstance(frozen["external_reference"], str)
        or not frozen["external_reference"].strip()
    ):
        raise ValueError("review_projection.external_reference n\u00e3o pode ser vazio.")
    declared_fields = frozen["declared_fields"]
    if not isinstance(declared_fields, MappingProxyType):
        raise TypeError("review_projection.declared_fields deve ser objeto.")
    if set(declared_fields) != _REVIEW_PROJECTION_FIELDS[resource_kind]:
        raise ValueError("review_projection.declared_fields viola a allowlist.")
    return frozen


@dataclass(frozen=True, slots=True)
class ExternalSourceCaptureAssociationReview:
    review_id: TypedId
    organization_id: OrganizationId
    capture_artifact_id: TypedId
    candidate_animal_id: TypedId
    status: ExternalSourceCaptureAssociationReviewStatus
    basis_code: str
    reviewed_by: TypedId
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_utc(self.reviewed_at, field_name="reviewed_at")
        if self.review_id.entity_type != "external_source_capture_association_review":
            raise ValueError("review_id inválido.")
        if self.capture_artifact_id.entity_type != "external_source_capture_artifact":
            raise ValueError("capture_artifact_id inválido.")
        if self.candidate_animal_id.entity_type != "animal":
            raise ValueError("candidate_animal_id deve ser animal.")
        if not self.basis_code.strip():
            raise ValueError("basis_code não pode ser vazio.")

        if self.reviewed_by.entity_type not in {"actor", "user", "system"}:
            raise ValueError("reviewed_by deve apontar para actor, user ou system.")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("limitations n\u00e3o pode conter texto vazio.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        capture_artifact_id: TypedId,
        candidate_animal_id: TypedId,
        status: ExternalSourceCaptureAssociationReviewStatus,
        basis_code: str,
        reviewed_by: TypedId,
        reviewed_at: datetime | None = None,
        limitations: tuple[str, ...] = (),
    ) -> "ExternalSourceCaptureAssociationReview":
        return cls(
            review_id=TypedId.new("external_source_capture_association_review"),
            organization_id=organization_id,
            capture_artifact_id=capture_artifact_id,
            candidate_animal_id=candidate_animal_id,
            status=status,
            basis_code=basis_code,
            reviewed_by=reviewed_by,
            reviewed_at=datetime.now(UTC) if reviewed_at is None else reviewed_at,
            limitations=limitations,
        )


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
    review_projection: MappingProxyType[str, Any] | None = None
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    limitations: tuple[str, ...] = ()
    projection_digest: str | None = field(default=None, init=False)

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
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("limitations n\u00e3o pode conter texto vazio.")
        if self.review_projection is not None:
            validated_projection = _validated_review_projection(
                self.review_projection, resource_kind=self.resource_kind
            )
            object.__setattr__(self, "review_projection", validated_projection)
            object.__setattr__(
                self,
                "projection_digest",
                _canonical_projection_digest(validated_projection),
            )
        if self.review_projection is not None and not isinstance(
            self.review_projection, MappingProxyType
        ):
            raise TypeError("review_projection deve ser imutável.")

    def supports_confirmed_candidate_review(self) -> bool:
        """Somente material capturado e parseado pode fundamentar review positiva."""
        return (
            self.transport_outcome == "CAPTURED"
            and self.response_status_code == 200
            and self.response_digest is not None
            and self.parsing_diagnostic_code is None
            and self.review_projection is not None
            and self.projection_digest is not None
        )

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
        review_projection: dict[str, Any] | None = None,
        limitations: tuple[str, ...] = (),
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
            review_projection=None
            if review_projection is None
            else MappingProxyType(dict(review_projection)),
            limitations=limitations,
        )
