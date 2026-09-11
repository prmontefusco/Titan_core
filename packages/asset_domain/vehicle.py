"""Agregado `Vehicle` — Titan Asset & Sustainment (A2, primeiro slice).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.1. Invariantes: `docs/asset/07_INVARIANTS.md`
I‑VEH‑1 (uma baseline vigente por vez), I‑VEH‑2 (leitura de medidor monotônica,
correção não apaga) e I‑VEH‑3 (transição de ciclo de vida monotônica e auditada;
`IN_MAINTENANCE`→`AVAILABLE` só via `return_to_service`, nunca pela transição
genérica). Decisão B1 (`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md`):
`Vehicle` é agregado da própria vertical `asset`.
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class VehicleLifecycleState(StrEnum):
    """`WAITING_MATERIAL` não é estado do veículo — é derivado da `WorkOrder`
    (`05_DOMAIN_MODEL.md` §1.1; revisão da ADR do slice §2)."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    MAINTENANCE_PLANNED = "MAINTENANCE_PLANNED"
    IN_MAINTENANCE = "IN_MAINTENANCE"
    UNAVAILABLE = "UNAVAILABLE"


class AssetOwnership(StrEnum):
    COMPANY = "COMPANY"
    CUSTOMER = "CUSTOMER"


class MeterKind(StrEnum):
    HOURS = "HOURS"
    KILOMETERS = "KILOMETERS"


# Transições genéricas permitidas (I‑VEH‑3). `IN_MAINTENANCE -> AVAILABLE`
# deliberadamente NÃO está aqui: só acontece via `return_to_service`, que exige
# `work_order_ref` + `validation_ref` (I‑WO‑1).
_ALLOWED_LIFECYCLE_TRANSITIONS: dict[VehicleLifecycleState, frozenset[VehicleLifecycleState]] = {
    VehicleLifecycleState.AVAILABLE: frozenset(
        {
            VehicleLifecycleState.DEGRADED,
            VehicleLifecycleState.MAINTENANCE_PLANNED,
            VehicleLifecycleState.UNAVAILABLE,
        }
    ),
    VehicleLifecycleState.DEGRADED: frozenset(
        {
            VehicleLifecycleState.AVAILABLE,
            VehicleLifecycleState.MAINTENANCE_PLANNED,
            VehicleLifecycleState.UNAVAILABLE,
        }
    ),
    VehicleLifecycleState.MAINTENANCE_PLANNED: frozenset(
        {
            VehicleLifecycleState.AVAILABLE,
            VehicleLifecycleState.DEGRADED,
            VehicleLifecycleState.IN_MAINTENANCE,
        }
    ),
    VehicleLifecycleState.IN_MAINTENANCE: frozenset(
        {
            VehicleLifecycleState.UNAVAILABLE,
        }
    ),
    VehicleLifecycleState.UNAVAILABLE: frozenset(
        {
            VehicleLifecycleState.AVAILABLE,
            VehicleLifecycleState.DEGRADED,
            VehicleLifecycleState.IN_MAINTENANCE,
        }
    ),
}


class TransicaoDeCicloDeVidaInvalida(ValueError):
    """Transição de `VehicleLifecycleState` fora da tabela permitida (I‑VEH‑3)."""


class LeituraDeMedidorRetrocedeu(ValueError):
    """Nova leitura de medidor menor que a última do mesmo tipo, sem correção (I‑VEH‑2)."""


class RetornoAoServicoInvalido(ValueError):
    """`return_to_service` chamado fora de `IN_MAINTENANCE`, ou sem validação (I‑VEH‑3, I‑WO‑1)."""


@dataclass(frozen=True, slots=True)
class VehicleIdentifiers:
    """VO — `05_DOMAIN_MODEL.md` §1.1."""

    serial_number: str
    chassis: str | None = None
    fleet_number: str | None = None

    def __post_init__(self) -> None:
        if not self.serial_number or not self.serial_number.strip():
            raise ValueError("serial_number não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class MeterReading:
    """VO append‑only. `05_DOMAIN_MODEL.md` §1.1; I‑VEH‑2."""

    reading_id: TypedId
    kind: MeterKind
    value: Decimal
    observed_at: datetime
    recorded_at: datetime
    source: str

    def __post_init__(self) -> None:
        require_utc(self.observed_at, field_name="observed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.reading_id.entity_type != "vehicle_meter_reading":
            raise ValueError(
                "reading_id deve ter entity_type 'vehicle_meter_reading', recebido "
                f"'{self.reading_id.entity_type}'."
            )
        if self.value < 0:
            raise ValueError("value de leitura de medidor não pode ser negativo.")
        if not self.source or not self.source.strip():
            raise ValueError("source não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class MeterCorrection:
    """VO append‑only. Corrige uma `MeterReading` sem apagá‑la (I‑VEH‑2, constituição §24)."""

    correction_id: TypedId
    original_reading_id: TypedId
    corrected_value: Decimal
    reason: str
    corrected_at: datetime

    def __post_init__(self) -> None:
        require_utc(self.corrected_at, field_name="corrected_at")
        if self.correction_id.entity_type != "vehicle_meter_correction":
            raise ValueError(
                "correction_id deve ter entity_type 'vehicle_meter_correction', recebido "
                f"'{self.correction_id.entity_type}'."
            )
        if self.corrected_value < 0:
            raise ValueError("corrected_value não pode ser negativo.")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason é obrigatório para corrigir uma leitura de medidor.")


@dataclass(frozen=True, slots=True)
class Vehicle:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.1; `06_AGGREGATE_ANALYSIS.md` §1."""

    vehicle_id: TypedId
    organization_id: OrganizationId
    model_ref: TypedId
    identifiers: VehicleIdentifiers
    ownership: AssetOwnership
    variant_ref: TypedId | None = None
    site_ref: TypedId | None = None
    current_baseline_ref: TypedId | None = None
    baseline_valid_from: datetime | None = None
    lifecycle_state: VehicleLifecycleState = VehicleLifecycleState.AVAILABLE
    meter_readings: tuple[MeterReading, ...] = ()
    meter_corrections: tuple[MeterCorrection, ...] = ()
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.created_at, field_name="created_at")
        if self.vehicle_id.entity_type != "vehicle":
            raise ValueError(
                "vehicle_id deve ter entity_type 'vehicle', recebido "
                f"'{self.vehicle_id.entity_type}'."
            )
        if self.model_ref.entity_type != "vehicle_model":
            raise ValueError(
                "model_ref deve ter entity_type 'vehicle_model', recebido "
                f"'{self.model_ref.entity_type}'."
            )
        if self.variant_ref is not None and self.variant_ref.entity_type != "vehicle_variant":
            raise ValueError(
                "variant_ref deve ter entity_type 'vehicle_variant', recebido "
                f"'{self.variant_ref.entity_type}'."
            )
        if self.site_ref is not None and self.site_ref.entity_type != "customer_site":
            raise ValueError(
                "site_ref deve ter entity_type 'customer_site', recebido "
                f"'{self.site_ref.entity_type}'."
            )
        if self.current_baseline_ref is not None:
            if self.current_baseline_ref.entity_type != "configuration_baseline":
                raise ValueError(
                    "current_baseline_ref deve ter entity_type 'configuration_baseline', recebido "
                    f"'{self.current_baseline_ref.entity_type}'."
                )
            if self.baseline_valid_from is None:
                raise ValueError(
                    "baseline_valid_from é obrigatório quando current_baseline_ref está definido "
                    "(I-VEH-1: a baseline vigente precisa de um instante de início)."
                )
            require_utc(self.baseline_valid_from, field_name="baseline_valid_from")
        elif self.baseline_valid_from is not None:
            raise ValueError("baseline_valid_from sem current_baseline_ref não faz sentido.")

    # --- I-VEH-1: configuração ------------------------------------------------

    def set_configuration_baseline(
        self, baseline_ref: TypedId, *, valid_from: datetime
    ) -> "Vehicle":
        """Troca a baseline vigente (I‑VEH‑1). A anterior deixa de ser vigente
        atomicamente — não há dois `current_baseline_ref` simultâneos porque o
        agregado só guarda um.
        """
        require_utc(valid_from, field_name="valid_from")
        if baseline_ref.entity_type != "configuration_baseline":
            raise ValueError(
                "baseline_ref deve ter entity_type 'configuration_baseline', recebido "
                f"'{baseline_ref.entity_type}'."
            )
        if self.baseline_valid_from is not None and valid_from < self.baseline_valid_from:
            raise ValueError(
                "valid_from da nova baseline não pode ser anterior ao da baseline vigente "
                f"({self.baseline_valid_from.isoformat()})."
            )
        return replace(
            self,
            current_baseline_ref=baseline_ref,
            baseline_valid_from=valid_from,
            version=self.version + 1,
        )

    # --- I-VEH-2: medidor -------------------------------------------------------

    def _last_reading(self, kind: MeterKind) -> MeterReading | None:
        candidates = [reading for reading in self.meter_readings if reading.kind == kind]
        if not candidates:
            return None
        return max(candidates, key=lambda reading: (reading.observed_at, reading.recorded_at))

    def record_meter_reading(self, reading: MeterReading) -> "Vehicle":
        """I‑VEH‑2: `value` novo ≥ o último do mesmo `kind`, salvo correção
        explícita via `correct_meter_reading`."""
        last = self._last_reading(reading.kind)
        if last is not None and reading.value < last.value:
            raise LeituraDeMedidorRetrocedeu(
                f"Nova leitura de {reading.kind.value} ({reading.value}) é menor que a última "
                f"registrada ({last.value}). Use correct_meter_reading para corrigir um valor "
                "errado sem apagar o histórico."
            )
        return replace(
            self, meter_readings=self.meter_readings + (reading,), version=self.version + 1
        )

    def correct_meter_reading(self, correction: MeterCorrection) -> "Vehicle":
        """A leitura original permanece; a correção é um registro aditivo
        (constituição §24, I‑VEH‑2)."""
        if not any(
            reading.reading_id == correction.original_reading_id for reading in self.meter_readings
        ):
            raise KeyError(
                f"Leitura '{correction.original_reading_id.value}' não encontrada neste veículo."
            )
        if any(
            existing.original_reading_id == correction.original_reading_id
            for existing in self.meter_corrections
        ):
            raise ValueError(
                f"Leitura '{correction.original_reading_id.value}' já tem correção registrada; "
                "corrigir a correção exige uma nova leitura, não uma segunda correção da mesma."
            )
        return replace(
            self,
            meter_corrections=self.meter_corrections + (correction,),
            version=self.version + 1,
        )

    # --- I-VEH-3: ciclo de vida --------------------------------------------------

    def transition_lifecycle(
        self, new_state: VehicleLifecycleState, *, reason: str | None = None
    ) -> "Vehicle":
        """Transição genérica (I‑VEH‑3). `IN_MAINTENANCE -> AVAILABLE` não é
        alcançável por aqui — ver `return_to_service`."""
        allowed = _ALLOWED_LIFECYCLE_TRANSITIONS.get(self.lifecycle_state, frozenset())
        if new_state not in allowed:
            raise TransicaoDeCicloDeVidaInvalida(
                f"Transição de '{self.lifecycle_state.value}' para '{new_state.value}' não é "
                "permitida. Se o destino é AVAILABLE a partir de IN_MAINTENANCE, use "
                "return_to_service (exige validação pós-manutenção — I-WO-1)."
            )
        return replace(self, lifecycle_state=new_state, version=self.version + 1)

    def return_to_service(self, *, work_order_ref: TypedId, validation_ref: TypedId) -> "Vehicle":
        """Única via de `IN_MAINTENANCE` para `AVAILABLE` (I‑VEH‑3, I‑WO‑1).
        `work_order_ref`/`validation_ref` são a evidência de que a validação
        pós‑manutenção passou — este método não a executa, só exige a referência
        (a garantia de que ela passou é responsabilidade de `sustainment_application`,
        que só chama isto depois de `PostMaintenanceValidation` bem-sucedida).
        """
        if self.lifecycle_state is not VehicleLifecycleState.IN_MAINTENANCE:
            raise RetornoAoServicoInvalido(
                f"return_to_service só é válido a partir de IN_MAINTENANCE, veículo está em "
                f"'{self.lifecycle_state.value}'."
            )
        if work_order_ref.entity_type != "work_order":
            raise ValueError(
                f"work_order_ref deve ter entity_type 'work_order', recebido "
                f"'{work_order_ref.entity_type}'."
            )
        if validation_ref.entity_type != "post_maintenance_validation":
            raise ValueError(
                "validation_ref deve ter entity_type 'post_maintenance_validation', recebido "
                f"'{validation_ref.entity_type}'."
            )
        return replace(
            self, lifecycle_state=VehicleLifecycleState.AVAILABLE, version=self.version + 1
        )
