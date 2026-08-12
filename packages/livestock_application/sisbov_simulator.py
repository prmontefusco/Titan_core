"""Contrato puro para capturar material do simulador SISBOV local.

O módulo não abre conexão HTTP, não persiste dados e não converte a resposta em
Fact, Evidence, coverage ou autoridade. O transporte concreto fica para corte futuro.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from urllib.parse import quote

from packages.shared_kernel import TypedId
from packages.shared_kernel.temporal import require_utc

SISBOV_SIMULATOR_SOURCE_CODE = "SISBOV_SIMULATOR_LOCAL"
SISBOV_SIMULATOR_SOURCE_CLASSIFICATION = "SIMULATED"


class SisbovSimulatorResource(StrEnum):
    ANIMAL = "ANIMAL"
    GTA = "GTA"
    MOVEMENT = "MOVEMENT"


class SisbovSimulatorCaptureStatus(StrEnum):
    CAPTURED = "CAPTURED"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"


class SisbovSimulatorParseStatus(StrEnum):
    PARSED = "PARSED"
    CAPTURE_UNAVAILABLE = "CAPTURE_UNAVAILABLE"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    IDENTIFIER_MISMATCH = "IDENTIFIER_MISMATCH"


@dataclass(frozen=True, slots=True)
class SisbovSimulatorRequest:
    resource: SisbovSimulatorResource
    lookup_value: str
    path: str

    def __post_init__(self) -> None:
        if not self.lookup_value.strip():
            raise ValueError("lookup_value não pode ser vazio.")
        if not self.path.startswith("/"):
            raise ValueError("path deve iniciar com '/'.")

    @classmethod
    def animal(cls, numero: str) -> "SisbovSimulatorRequest":
        return cls(
            SisbovSimulatorResource.ANIMAL,
            numero,
            f"/animal/{quote(numero, safe='')}/getAnimalPorNumero",
        )

    @classmethod
    def gta(cls, numero_completo: str) -> "SisbovSimulatorRequest":
        return cls(
            SisbovSimulatorResource.GTA,
            numero_completo,
            f"/gta/{quote(numero_completo, safe='')}/getGTAPorNumeroCompleto",
        )

    @classmethod
    def movement_by_gta(cls, numero_composto: str) -> "SisbovSimulatorRequest":
        return cls(
            SisbovSimulatorResource.MOVEMENT,
            numero_composto,
            f"/gta/{quote(numero_composto, safe='')}/movimentacao",
        )


@dataclass(frozen=True, slots=True)
class SisbovSimulatorTransportResponse:
    status_code: int | None
    body: bytes | None
    received_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.received_at, field_name="received_at")
        if self.status_code is not None and not 100 <= self.status_code <= 599:
            raise ValueError("status_code deve ser HTTP válido ou None.")


class SisbovSimulatorTransportPort(Protocol):
    def get(self, request: SisbovSimulatorRequest) -> SisbovSimulatorTransportResponse: ...


@dataclass(frozen=True, slots=True)
class SisbovSimulatorCapture:
    request: SisbovSimulatorRequest
    status: SisbovSimulatorCaptureStatus
    captured_at: datetime
    response_status_code: int | None
    response_digest: str | None
    response_body: bytes | None
    source_code: str = SISBOV_SIMULATOR_SOURCE_CODE
    source_classification: str = SISBOV_SIMULATOR_SOURCE_CLASSIFICATION

    def __post_init__(self) -> None:
        require_utc(self.captured_at, field_name="captured_at")
        if self.source_code != SISBOV_SIMULATOR_SOURCE_CODE:
            raise ValueError("O Corte 1 suporta apenas a fonte do simulador SISBOV.")
        if self.source_classification != SISBOV_SIMULATOR_SOURCE_CLASSIFICATION:
            raise ValueError("A fonte deve permanecer marcada como SIMULATED.")
        if self.response_body is None and self.response_digest is not None:
            raise ValueError("response_digest exige response_body.")
        if self.response_body is not None:
            digest = sha256(self.response_body).hexdigest()
            if self.response_digest != digest:
                raise ValueError("response_digest não confere com response_body.")


@dataclass(frozen=True, slots=True)
class SisbovSimulatorCaptureService:
    transport: SisbovSimulatorTransportPort

    def capture(self, request: SisbovSimulatorRequest) -> SisbovSimulatorCapture:
        response = self.transport.get(request)
        return SisbovSimulatorCapture(
            request=request,
            status=_capture_status(response.status_code),
            captured_at=response.received_at,
            response_status_code=response.status_code,
            response_digest=None if response.body is None else sha256(response.body).hexdigest(),
            response_body=response.body,
        )


@dataclass(frozen=True, slots=True)
class SisbovAnimalObservation:
    numero: str
    external_id: str
    status: str | None
    local_property_eras: str | None


@dataclass(frozen=True, slots=True)
class SisbovGtaObservation:
    numero_completo: str
    external_id: str
    status: str | None
    issued_on: str | None
    origin_property_eras: str | None
    destination_property_eras: str | None


@dataclass(frozen=True, slots=True)
class SisbovMovementObservation:
    external_id: str
    status: str
    gta_references: tuple[str, ...]
    animal_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SisbovSimulatorParseResult:
    status: SisbovSimulatorParseStatus
    observation: SisbovAnimalObservation | SisbovGtaObservation | SisbovMovementObservation | None
    diagnostic_code: str | None = None


@dataclass(frozen=True, slots=True)
class SisbovSimulatorParser:
    """Interpreta apenas o contrato mínimo do simulador, sem efeitos de domínio."""

    def parse(self, capture: SisbovSimulatorCapture) -> SisbovSimulatorParseResult:
        if capture.status is not SisbovSimulatorCaptureStatus.CAPTURED:
            return SisbovSimulatorParseResult(
                SisbovSimulatorParseStatus.CAPTURE_UNAVAILABLE,
                None,
                f"CAPTURE_{capture.status.value}",
            )
        body = _json_object(capture.response_body)
        if body is None:
            return SisbovSimulatorParseResult(
                SisbovSimulatorParseStatus.MALFORMED_RESPONSE,
                None,
                "SIMULATOR_RESPONSE_NOT_JSON_OBJECT",
            )
        if capture.request.resource is SisbovSimulatorResource.ANIMAL:
            return self._animal(capture.request, body)
        if capture.request.resource is SisbovSimulatorResource.GTA:
            return self._gta(capture.request, body)
        return self._movement(body)

    @staticmethod
    def _animal(
        request: SisbovSimulatorRequest, body: dict[str, object]
    ) -> SisbovSimulatorParseResult:
        numero, external_id = _string(body, "numero"), _string(body, "id")
        if numero is None or external_id is None:
            return _malformed("SIMULATOR_ANIMAL_REQUIRED_FIELDS_ABSENT")
        if numero != request.lookup_value:
            return SisbovSimulatorParseResult(
                SisbovSimulatorParseStatus.IDENTIFIER_MISMATCH,
                None,
                "SIMULATOR_ANIMAL_NUMBER_MISMATCH",
            )
        return SisbovSimulatorParseResult(
            SisbovSimulatorParseStatus.PARSED,
            SisbovAnimalObservation(
                numero,
                external_id,
                _string(body, "statusAnimal"),
                _string(body, "ERASPropriedadeLocalizacao"),
            ),
        )

    @staticmethod
    def _gta(
        request: SisbovSimulatorRequest, body: dict[str, object]
    ) -> SisbovSimulatorParseResult:
        numero, external_id = _string(body, "numeroCompleto"), _string(body, "id")
        if numero is None or external_id is None:
            return _malformed("SIMULATOR_GTA_REQUIRED_FIELDS_ABSENT")
        if numero != request.lookup_value:
            return SisbovSimulatorParseResult(
                SisbovSimulatorParseStatus.IDENTIFIER_MISMATCH,
                None,
                "SIMULATOR_GTA_NUMBER_MISMATCH",
            )
        return SisbovSimulatorParseResult(
            SisbovSimulatorParseStatus.PARSED,
            SisbovGtaObservation(
                numero,
                external_id,
                _string(body, "status"),
                _string(body, "dataEmissao"),
                _string(body, "ERASPropriedadeOrigem"),
                _string(body, "ERASPropriedadeDestino"),
            ),
        )

    @staticmethod
    def _movement(body: dict[str, object]) -> SisbovSimulatorParseResult:
        external_id, status = _string(body, "id"), _string(body, "statusMovimentacao")
        gtas, animals = body.get("gtas"), body.get("animais")
        if (
            external_id is None
            or status is None
            or not isinstance(gtas, list)
            or not isinstance(animals, list)
        ):
            return _malformed("SIMULATOR_MOVEMENT_REQUIRED_FIELDS_ABSENT")
        gta_references = _references(gtas, "numeroComposto")
        animal_references = _references(animals, "numero")
        if gta_references is None or animal_references is None:
            return _malformed("SIMULATOR_MOVEMENT_REFERENCES_MALFORMED")
        return SisbovSimulatorParseResult(
            SisbovSimulatorParseStatus.PARSED,
            SisbovMovementObservation(external_id, status, gta_references, animal_references),
        )


class SisbovSimulatorAssociationStatus(StrEnum):
    UNMATCHED = "UNMATCHED"
    UNIQUE_CANDIDATE = "UNIQUE_CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class SisbovSimulatorAssociationAssessment:
    external_animal_number: str
    status: SisbovSimulatorAssociationStatus
    candidate_animal_ids: tuple[TypedId, ...]


@dataclass(frozen=True, slots=True)
class SisbovSimulatorAssociationService:
    """Expõe candidatos; nunca associa nem modifica um Animal Titan."""

    def assess(
        self, *, external_animal_number: str, candidate_animal_ids: tuple[TypedId, ...]
    ) -> SisbovSimulatorAssociationAssessment:
        if not external_animal_number.strip():
            raise ValueError("external_animal_number não pode ser vazio.")
        if any(item.entity_type != "animal" for item in candidate_animal_ids):
            raise ValueError("Candidatos devem ter entity_type 'animal'.")
        candidates = tuple(dict.fromkeys(candidate_animal_ids))
        status = (
            SisbovSimulatorAssociationStatus.UNMATCHED
            if not candidates
            else SisbovSimulatorAssociationStatus.UNIQUE_CANDIDATE
            if len(candidates) == 1
            else SisbovSimulatorAssociationStatus.AMBIGUOUS
        )
        return SisbovSimulatorAssociationAssessment(external_animal_number, status, candidates)


def _capture_status(status_code: int | None) -> SisbovSimulatorCaptureStatus:
    if status_code is None or status_code >= 500:
        return SisbovSimulatorCaptureStatus.TEMPORARY_FAILURE
    if status_code == 401:
        return SisbovSimulatorCaptureStatus.UNAUTHORIZED
    if status_code == 403:
        return SisbovSimulatorCaptureStatus.FORBIDDEN
    if status_code == 404:
        return SisbovSimulatorCaptureStatus.NOT_FOUND
    return SisbovSimulatorCaptureStatus.CAPTURED


def _json_object(body: bytes | None) -> dict[str, object] | None:
    if body is None:
        return None
    try:
        decoded = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _string(body: dict[str, object], key: str) -> str | None:
    value = body.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _references(items: list[object], key: str) -> tuple[str, ...] | None:
    references: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            return None
        value = item.get(key)
        if value is not None and not isinstance(value, str):
            return None
        if isinstance(value, str) and value.strip():
            references.append(value)
    return tuple(references)


def _malformed(code: str) -> SisbovSimulatorParseResult:
    return SisbovSimulatorParseResult(SisbovSimulatorParseStatus.MALFORMED_RESPONSE, None, code)
