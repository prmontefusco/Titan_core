"""Coverage sanitária controlada do NEXT-01, sem representar mercado real."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from packages.core_domain.facts import Fact
from packages.shared_kernel.temporal import require_utc

SANITARY_TEST_A_POLICY_CODE = "SANITARY_TEST_A_v1"
SANITARY_TEST_A_PURPOSE = "sanitary-test-a"
TREATMENT_HISTORY_COVERAGE_FACT_TYPE = "livestock.coverage.treatment_history"
TREATMENT_HISTORY_WINDOW_DAYS = 90


class TreatmentCoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ABSENT = "ABSENT"
    INACCESSIBLE = "INACCESSIBLE"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"


class TreatmentMaterialSource(StrEnum):
    LOCAL_TREATMENT_APPLICATION = "LOCAL_TREATMENT_APPLICATION"
    IMPORTED_DOCUMENTED = "IMPORTED_DOCUMENTED"
    INFORMED_ONLY = "INFORMED_ONLY"


class TreatmentMaterialAdmissibility(StrEnum):
    ADMISSIBLE = "ADMISSIBLE"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class TreatmentCoverageDeclaration:
    known_from: datetime | None
    known_until: datetime | None
    source: TreatmentMaterialSource
    accessible: bool = True
    conflicting: bool = False

    def __post_init__(self) -> None:
        if self.known_from is not None:
            require_utc(self.known_from, field_name="known_from")
        if self.known_until is not None:
            require_utc(self.known_until, field_name="known_until")
        if (
            self.known_from is not None
            and self.known_until is not None
            and self.known_from > self.known_until
        ):
            raise ValueError("known_from nao pode ser posterior a known_until.")


@dataclass(frozen=True, slots=True)
class AntimicrobialTreatmentRecord:
    occurred_at: datetime
    source: TreatmentMaterialSource
    source_artifact_id: str | None = None

    def __post_init__(self) -> None:
        require_utc(self.occurred_at, field_name="occurred_at")
        if self.source is TreatmentMaterialSource.IMPORTED_DOCUMENTED:
            if self.source_artifact_id is None or not self.source_artifact_id.strip():
                raise ValueError("Tratamento importado documentado exige source_artifact_id.")
        elif self.source_artifact_id is not None:
            raise ValueError("source_artifact_id pertence apenas ao material importado.")


@dataclass(frozen=True, slots=True)
class SanitaryTestACoverageService:
    """Deriva o fato consumido pela Policy fictícia SANITARY_TEST_A_v1.

    Coverage, validação estrutural e admissibilidade permanecem dimensões
    separadas. A chave conclusiva só existe quando a pergunta pode ser avaliada;
    assim, o motor Core produz INDETERMINADA para lacuna, em vez de reprovação.
    """

    def build_fact(
        self,
        *,
        reference_time: datetime,
        declaration: TreatmentCoverageDeclaration | None,
        treatments: tuple[AntimicrobialTreatmentRecord, ...] = (),
    ) -> Fact:
        require_utc(reference_time, field_name="reference_time")
        required_from = reference_time - timedelta(days=TREATMENT_HISTORY_WINDOW_DAYS)
        status = self._coverage_status(declaration, required_from, reference_time)
        admissibility = self._admissibility(declaration)

        payload: dict[str, object] = {
            "policy_code": SANITARY_TEST_A_POLICY_CODE,
            "dimension": "treatment_history",
            "required_from": required_from.isoformat(),
            "required_until": reference_time.isoformat(),
            "coverage_status": status.value,
            "admissibility": admissibility.value,
            "source": None if declaration is None else declaration.source.value,
            "limitations": self._limitations(status, admissibility),
        }

        if status is TreatmentCoverageStatus.COMPLETE and (
            admissibility is TreatmentMaterialAdmissibility.ADMISSIBLE
        ):
            payload["has_antimicrobial_treatment"] = any(
                required_from <= item.occurred_at <= reference_time
                and self._record_is_admissible(item)
                for item in treatments
            )

        return Fact.create(
            fact_type=TREATMENT_HISTORY_COVERAGE_FACT_TYPE,
            payload=payload,
            observed_at=reference_time,
        )

    @staticmethod
    def _coverage_status(
        declaration: TreatmentCoverageDeclaration | None,
        required_from: datetime,
        reference_time: datetime,
    ) -> TreatmentCoverageStatus:
        if declaration is None:
            return TreatmentCoverageStatus.ABSENT
        if not declaration.accessible:
            return TreatmentCoverageStatus.INACCESSIBLE
        if declaration.conflicting:
            return TreatmentCoverageStatus.CONFLICTING
        if declaration.known_from is None or declaration.known_until is None:
            return TreatmentCoverageStatus.UNKNOWN
        if declaration.known_from <= required_from and declaration.known_until >= reference_time:
            return TreatmentCoverageStatus.COMPLETE
        return TreatmentCoverageStatus.PARTIAL

    @staticmethod
    def _admissibility(
        declaration: TreatmentCoverageDeclaration | None,
    ) -> TreatmentMaterialAdmissibility:
        if declaration is None or declaration.source is TreatmentMaterialSource.INFORMED_ONLY:
            return TreatmentMaterialAdmissibility.INSUFFICIENT
        return TreatmentMaterialAdmissibility.ADMISSIBLE

    @staticmethod
    def _record_is_admissible(record: AntimicrobialTreatmentRecord) -> bool:
        return record.source in {
            TreatmentMaterialSource.LOCAL_TREATMENT_APPLICATION,
            TreatmentMaterialSource.IMPORTED_DOCUMENTED,
        }

    @staticmethod
    def _limitations(
        status: TreatmentCoverageStatus,
        admissibility: TreatmentMaterialAdmissibility,
    ) -> list[str]:
        limitations: list[str] = []
        if status is not TreatmentCoverageStatus.COMPLETE:
            limitations.append(f"TREATMENT_COVERAGE_{status.value}")
        if admissibility is not TreatmentMaterialAdmissibility.ADMISSIBLE:
            limitations.append("TREATMENT_MATERIAL_NOT_ADMISSIBLE")
        return limitations
