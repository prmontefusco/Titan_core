"""Corte 1 do POST-LIV-03: captura simulada sem efeitos de domínio."""

from dataclasses import dataclass
from datetime import UTC, datetime

from packages.livestock_application.sisbov_simulator import (
    SISBOV_SIMULATOR_SOURCE_CLASSIFICATION,
    SisbovAnimalObservation,
    SisbovMovementObservation,
    SisbovSimulatorAssociationService,
    SisbovSimulatorAssociationStatus,
    SisbovSimulatorCapture,
    SisbovSimulatorCaptureService,
    SisbovSimulatorCaptureStatus,
    SisbovSimulatorParser,
    SisbovSimulatorParseStatus,
    SisbovSimulatorRequest,
    SisbovSimulatorTransportResponse,
)
from packages.shared_kernel import TypedId

NOW = datetime(2026, 8, 12, tzinfo=UTC)


@dataclass
class FakeTransport:
    response: SisbovSimulatorTransportResponse
    received_request: SisbovSimulatorRequest | None = None

    def get(self, request: SisbovSimulatorRequest) -> SisbovSimulatorTransportResponse:
        self.received_request = request
        return self.response


def _capture(
    request: SisbovSimulatorRequest, body: bytes, status_code: int = 200
) -> SisbovSimulatorCapture:
    transport = FakeTransport(SisbovSimulatorTransportResponse(status_code, body, NOW))
    capture = SisbovSimulatorCaptureService(transport).capture(request)
    assert transport.received_request == request
    return capture


def test_captura_animal_preserva_digest_e_marcacao_simulada() -> None:
    request = SisbovSimulatorRequest.animal("BR0001")
    capture = _capture(
        request,
        b'{"id":"animal-ext-1","numero":"BR0001","statusAnimal":"ATIVO"}',
    )

    assert capture.status is SisbovSimulatorCaptureStatus.CAPTURED
    assert capture.source_classification == SISBOV_SIMULATOR_SOURCE_CLASSIFICATION
    assert capture.response_digest == (
        "004a8da549f5b706710dc93ba1511150b0bd6f2b1dd46e36125a38f7b06e6e3e"
    )
    parsed = SisbovSimulatorParser().parse(capture)
    assert parsed.status is SisbovSimulatorParseStatus.PARSED
    assert parsed.observation == SisbovAnimalObservation("BR0001", "animal-ext-1", "ATIVO", None)


def test_parser_recusa_numero_de_animal_divergente() -> None:
    capture = _capture(
        SisbovSimulatorRequest.animal("BR0001"),
        b'{"id":"animal-ext-1","numero":"BR9999"}',
    )

    parsed = SisbovSimulatorParser().parse(capture)

    assert parsed.status is SisbovSimulatorParseStatus.IDENTIFIER_MISMATCH
    assert parsed.diagnostic_code == "SIMULATOR_ANIMAL_NUMBER_MISMATCH"


def test_parser_le_gta_e_movimentacao_sem_concluir_ocorrencia() -> None:
    gta = SisbovSimulatorParser().parse(
        _capture(
            SisbovSimulatorRequest.gta("MS123"),
            b'{"id":"gta-ext-1","numeroCompleto":"MS123","status":"EMITIDA",'
            b'"dataEmissao":"2026-08-01","ERASPropriedadeOrigem":"101",'
            b'"ERASPropriedadeDestino":"202"}',
        )
    )
    movement = SisbovSimulatorParser().parse(
        _capture(
            SisbovSimulatorRequest.movement_by_gta("MS123"),
            b'{"id":"mov-ext-1","statusMovimentacao":"ABERTA",'
            b'"gtas":[{"numeroComposto":"MS123"}],"animais":[{"numero":"BR0001"}]}',
        )
    )

    assert gta.status is SisbovSimulatorParseStatus.PARSED
    assert movement.status is SisbovSimulatorParseStatus.PARSED
    assert isinstance(movement.observation, SisbovMovementObservation)
    assert movement.observation.gta_references == ("MS123",)
    assert movement.observation.animal_references == ("BR0001",)


def test_falhas_de_transporte_e_corpo_malformado_permanecem_explicitas() -> None:
    request = SisbovSimulatorRequest.gta("MS123")
    missing = _capture(request, b'{"error":"ausente"}', 404)
    malformed = _capture(request, b"not-json")

    missing_result = SisbovSimulatorParser().parse(missing)
    malformed_result = SisbovSimulatorParser().parse(malformed)

    assert missing_result.status is SisbovSimulatorParseStatus.CAPTURE_UNAVAILABLE
    assert missing_result.diagnostic_code == "CAPTURE_NOT_FOUND"
    assert malformed_result.status is SisbovSimulatorParseStatus.MALFORMED_RESPONSE
    assert malformed_result.diagnostic_code == "SIMULATOR_RESPONSE_NOT_JSON_OBJECT"


def test_associacao_expoe_ambiguidade_sem_alterar_animal() -> None:
    result = SisbovSimulatorAssociationService().assess(
        external_animal_number="BR0001",
        candidate_animal_ids=(TypedId.new("animal"), TypedId.new("animal")),
    )

    assert result.status is SisbovSimulatorAssociationStatus.AMBIGUOUS
    assert len(result.candidate_animal_ids) == 2
