from datetime import UTC, datetime, timedelta

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.acquisition_continuity_service import (
    DocumentaryAcquisitionService,
    DocumentaryImportedFactInput,
)
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.imported_fact_service import ImportedLivestockFactService
from packages.livestock_domain.events import IMPORTED_FACT_RECORDED, TRANSFER_ARTIFACT_RECEIVED
from packages.shared_kernel import TypedId
from tests.livestock_application.conftest import FakeEventLog
from tests.livestock_application.test_imported_fact_service import InMemoryImportedFactRepo
from tests.livestock_application.test_transfer_artifact_service import _service as artifact_service


def _build_service(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> tuple[DocumentaryAcquisitionService, TypedId, TypedId]:
    transfer_service, animal_id, counterparty_id = artifact_service(recorder, context)
    service = DocumentaryAcquisitionService(
        artifact_service=transfer_service,
        imported_fact_service=ImportedLivestockFactService(
            repository=InMemoryImportedFactRepo(),
            artifact_repository=transfer_service.repository,
            animal_repository=transfer_service.animal_repository,
            recorder=recorder,
        ),
    )
    return service, animal_id, counterparty_id


def test_orquestra_aquisicao_documental_sem_novo_agregado(
    recorder: LivestockEventRecorder,
    event_log: FakeEventLog,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, counterparty_id = _build_service(recorder, context)
    transferencia = datetime.now(UTC) - timedelta(days=1)

    resultado = service.register_documentary_acquisition(
        context=context,
        animal_id=animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="a" * 64,
        bundle_issued_at=transferencia,
        transfer_effective_at=transferencia,
        coverage_known_from=transferencia - timedelta(days=180),
        coverage_known_until=transferencia,
        imported_facts=(
            DocumentaryImportedFactInput(
                fact_type="livestock.treatment_applied",
                occurred_at=transferencia - timedelta(days=30),
                asserted_by="Fazenda Origem",
                confidence_tier=ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED,
                payload={"withdrawal_period_days": 45},
            ),
        ),
    )

    assert resultado.artifact.animal_id == animal_id
    assert len(resultado.imported_facts) == 1
    assert resultado.imported_facts[0].source_artifact_id == resultado.artifact.artifact_id
    assert event_log.only(TRANSFER_ARTIFACT_RECEIVED).aggregate_reference.target_id == (
        resultado.artifact.artifact_id
    )
    assert event_log.only(IMPORTED_FACT_RECORDED).aggregate_reference.target_id == (
        resultado.imported_facts[0].imported_fact_id
    )


def test_aquisicao_documental_sem_fato_importado_preserva_lacuna_explicita(
    recorder: LivestockEventRecorder,
    context: LivestockOperationContext,
) -> None:
    service, animal_id, counterparty_id = _build_service(recorder, context)
    transferencia = datetime.now(UTC) - timedelta(days=1)

    resultado = service.register_documentary_acquisition(
        context=context,
        animal_id=animal_id,
        source_counterparty_id=counterparty_id,
        bundle_digest="b" * 64,
        bundle_issued_at=transferencia - timedelta(hours=12),
        transfer_effective_at=transferencia,
        coverage_known_from=None,
        coverage_known_until=None,
    )

    assert resultado.imported_facts == ()
    assert resultado.artifact.coverage.gaps[0].code.value == "HISTORY_BEFORE_ACQUISITION_UNKNOWN"
