"""Agregados de inventário — Titan Asset & Sustainment (A2).

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §1.7‑1.10. Invariantes:
`docs/asset/07_INVARIANTS.md` I‑INV‑0 (peça sem estoque implícito — já garantido
em `part.py`, `Part` não tem campo de quantidade), I‑INV‑1 (`available ≥ 0`,
sempre calculado com breakdown), I‑INV‑2 (disputa produz `Decision` — o campo
`decision_ref` existe aqui; a política que a decide é do Core/aplicação, não
deste módulo), I‑INV‑3 (concorrência — `version` obrigatório; o `SELECT ... FOR
UPDATE` é de infraestrutura, A3) e I‑INV‑4 (transferência conserva quantidade).

**`StockPosition` não contém `StockReservation` inteira** — `06_AGGREGATE_ANALYSIS.md`
§3: a reserva tem ciclo de vida próprio (é criada por outra transação, no
cenário B é assíncrona). `StockPosition.reservations` guarda só a **projeção**
(`StockReservationLine`) usada para calcular `available`; `StockReservation` é
agregado separado, coordenado pela aplicação, não aninhado aqui.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId


class StockLocationKind(StrEnum):
    CENTRAL_WAREHOUSE = "CENTRAL_WAREHOUSE"
    REGIONAL_WAREHOUSE = "REGIONAL_WAREHOUSE"
    WORKSHOP = "WORKSHOP"
    OM_STOCK = "OM_STOCK"


class StockPurpose(StrEnum):
    PRODUCTION = "PRODUCTION"
    SERVICE_SLI = "SERVICE_SLI"
    OM_REMOTE = "OM_REMOTE"
    COMMERCIAL = "COMMERCIAL"


class StockOwnership(StrEnum):
    COMPANY_OWNED = "COMPANY_OWNED"
    CUSTOMER_OWNED = "CUSTOMER_OWNED"
    CONSIGNMENT = "CONSIGNMENT"


class ReservationState(StrEnum):
    HELD = "HELD"
    ALLOCATED = "ALLOCATED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"


class DemandKind(StrEnum):
    WORK_ORDER = "WORK_ORDER"
    PRODUCTION_ORDER = "PRODUCTION_ORDER"
    SALES_ORDER = "SALES_ORDER"


class TransferState(StrEnum):
    """Unifica `DISPATCHED`/`IN_TRANSIT` de `05_DOMAIN_MODEL.md` §1.10 numa só
    transição (`dispatch`): `08_DOMAIN_EVENTS.md` só declara
    `transfer_dispatched`/`transfer_received`, sem evento para um momento
    "em trânsito" distinto do despacho — os dois não são observáveis
    separadamente no slice. Revisitar se isso mudar."""

    REQUESTED = "REQUESTED"
    IN_TRANSIT = "IN_TRANSIT"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"


class DisponibilidadeInsuficiente(ValueError):
    """`qty` solicitada excede `available` na posição (I‑INV‑1)."""


class PropositoIncompativel(ValueError):
    """Reserva de propósito diferente do da posição sem `decision_ref` (I‑INV‑2)."""


class TransicaoDeReservaInvalida(ValueError):
    """Transição de `ReservationState` fora da máquina de estados."""


class TransicaoDeTransferenciaInvalida(ValueError):
    """Transição de `TransferState` fora da máquina de estados."""


class RecebimentoExcedeDespacho(ValueError):
    """`Σ recebido > qty despachada` (I‑INV‑4)."""


@dataclass(frozen=True, slots=True)
class StockLocation:
    """`05_DOMAIN_MODEL.md` §1.7. Entidade de referência — sem invariante
    transacional forte (`06_AGGREGATE_ANALYSIS.md` §2)."""

    location_id: TypedId
    organization_id: OrganizationId
    kind: StockLocationKind
    code: str
    display_name: str
    site_ref: TypedId | None = None

    def __post_init__(self) -> None:
        if self.location_id.entity_type != "stock_location":
            raise ValueError(
                "location_id deve ter entity_type 'stock_location', recebido "
                f"'{self.location_id.entity_type}'."
            )
        if self.site_ref is not None and self.site_ref.entity_type != "customer_site":
            raise ValueError(
                "site_ref deve ter entity_type 'customer_site', recebido "
                f"'{self.site_ref.entity_type}'."
            )
        if not self.code or not self.code.strip():
            raise ValueError("code não pode ser vazio.")
        if not self.display_name or not self.display_name.strip():
            raise ValueError("display_name não pode ser vazio.")


def _require_non_negative(value: Decimal, *, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} não pode ser negativo, recebido {value}.")


@dataclass(frozen=True, slots=True)
class StockQuantities:
    """VO — `05_DOMAIN_MODEL.md` §1.8. Cada bucket é não‑negativo
    individualmente (I‑INV‑3; achado de `docs/asset/09_COMMAND_MODEL.md`
    `AdjustStock`: ajuste nomeia o bucket, nunca é genérico)."""

    on_hand: Decimal = Decimal(0)
    in_transit: Decimal = Decimal(0)
    quarantine: Decimal = Decimal(0)
    inspection: Decimal = Decimal(0)
    damaged: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        for field_name in ("on_hand", "in_transit", "quarantine", "inspection", "damaged"):
            _require_non_negative(getattr(self, field_name), field_name=field_name)

    def adjust(self, **deltas: Decimal) -> "StockQuantities":
        """`deltas` nomeia o(s) bucket(s) alvo (I‑INV‑3). Cada resultante ≥ 0."""
        unknown = set(deltas) - set(self.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Bucket(s) desconhecido(s) em AdjustStock: {sorted(unknown)}.")
        updated = {name: getattr(self, name) + delta for name, delta in deltas.items()}
        return replace(self, **updated)


@dataclass(frozen=True, slots=True)
class AvailabilityBreakdown:
    """VO de resposta — nunca um booleano solto (I‑INV‑1, constituição §1, §42)."""

    on_hand: Decimal
    reserved: Decimal
    quarantine: Decimal
    inspection: Decimal
    damaged: Decimal

    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved - self.quarantine - self.inspection - self.damaged


@dataclass(frozen=True, slots=True)
class StockReservationLine:
    """VO — projeção de uma `StockReservation` ativa dentro de `StockPosition`
    (`06_AGGREGATE_ANALYSIS.md` §3). `purpose_lock` é o propósito da demanda
    que gerou esta linha — pode divergir do `purpose` da posição (I‑INV‑2)."""

    reservation_id: TypedId
    demand_ref: TypedId
    qty: Decimal
    priority: int
    purpose_lock: StockPurpose

    def __post_init__(self) -> None:
        if self.reservation_id.entity_type != "stock_reservation":
            raise ValueError(
                "reservation_id deve ter entity_type 'stock_reservation', recebido "
                f"'{self.reservation_id.entity_type}'."
            )
        _require_non_negative(self.qty, field_name="qty")
        if self.qty == 0:
            raise ValueError("qty de uma reserva deve ser > 0.")


@dataclass(frozen=True, slots=True)
class StockPosition:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.8; I‑INV‑1, I‑INV‑2, I‑INV‑3."""

    stock_position_id: TypedId
    organization_id: OrganizationId
    part_ref: TypedId
    location_ref: TypedId
    purpose: StockPurpose
    ownership: StockOwnership
    quantities: StockQuantities = StockQuantities()
    reservations: tuple[StockReservationLine, ...] = ()
    lot: str | None = None
    serial: str | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.stock_position_id.entity_type != "stock_position":
            raise ValueError(
                "stock_position_id deve ter entity_type 'stock_position', recebido "
                f"'{self.stock_position_id.entity_type}'."
            )
        if self.part_ref.entity_type != "part":
            raise ValueError(
                f"part_ref deve ter entity_type 'part', recebido '{self.part_ref.entity_type}'."
            )
        if self.location_ref.entity_type != "stock_location":
            raise ValueError(
                "location_ref deve ter entity_type 'stock_location', recebido "
                f"'{self.location_ref.entity_type}'."
            )
        ids = [line.reservation_id for line in self.reservations]
        if len(set(ids)) != len(ids):
            raise ValueError("reservations não pode repetir o mesmo reservation_id.")
        # I-INV-1, na construção: a soma das reservas nunca excede on_hand
        # líquido de quarentena/inspeção/dano.
        if self._reserved_qty() > self._headroom():
            raise DisponibilidadeInsuficiente(
                "Σ reservations.qty excede on_hand - quarantine - inspection - damaged."
            )

    def _reserved_qty(self) -> Decimal:
        total = Decimal(0)
        for line in self.reservations:
            total += line.qty
        return total

    def _headroom(self) -> Decimal:
        q = self.quantities
        return q.on_hand - q.quarantine - q.inspection - q.damaged

    @property
    def available(self) -> Decimal:
        """I‑INV‑1: sempre calculado, nunca armazenado."""
        return self._headroom() - self._reserved_qty()

    def availability_breakdown(self) -> AvailabilityBreakdown:
        q = self.quantities
        return AvailabilityBreakdown(
            on_hand=q.on_hand,
            reserved=self._reserved_qty(),
            quarantine=q.quarantine,
            inspection=q.inspection,
            damaged=q.damaged,
        )

    def hold(
        self, line: StockReservationLine, *, cross_purpose_decision_ref: TypedId | None = None
    ) -> "StockPosition":
        """I‑INV‑1 (não excede `available`) + I‑INV‑2 (propósito divergente
        exige `decision_ref` de uma `Decision` do Core, resolvida pela
        aplicação **antes** de chamar isto — cenário C)."""
        if any(existing.reservation_id == line.reservation_id for existing in self.reservations):
            raise ValueError(f"Reserva '{line.reservation_id.value}' já existe nesta posição.")
        if line.purpose_lock != self.purpose and cross_purpose_decision_ref is None:
            raise PropositoIncompativel(
                f"Reserva de propósito '{line.purpose_lock.value}' numa posição "
                f"'{self.purpose.value}' exige decision_ref (I-INV-2, cenário C)."
            )
        if line.qty > self.available:
            raise DisponibilidadeInsuficiente(
                f"Reserva de {line.qty} excede o disponível ({self.available})."
            )
        return replace(self, reservations=self.reservations + (line,), version=self.version + 1)

    def release(self, reservation_id: TypedId) -> "StockPosition":
        if not any(line.reservation_id == reservation_id for line in self.reservations):
            raise KeyError(f"Reserva '{reservation_id.value}' não encontrada nesta posição.")
        return replace(
            self,
            reservations=tuple(
                line for line in self.reservations if line.reservation_id != reservation_id
            ),
            version=self.version + 1,
        )

    def consume(self, reservation_id: TypedId, qty: Decimal) -> "StockPosition":
        """Baixa física: `on_hand -= qty`; a linha de reserva correspondente
        sai da projeção (I‑WO‑2: `qty` já foi validada ≤ demandado pela
        aplicação antes de chegar aqui)."""
        line = next(
            (line for line in self.reservations if line.reservation_id == reservation_id), None
        )
        if line is None:
            raise KeyError(f"Reserva '{reservation_id.value}' não encontrada nesta posição.")
        if qty > line.qty:
            raise ValueError(
                f"Consumo de {qty} excede a quantidade reservada nesta linha ({line.qty})."
            )
        remaining = tuple(
            existing for existing in self.reservations if existing.reservation_id != reservation_id
        )
        if qty < line.qty:
            remaining = remaining + (replace(line, qty=line.qty - qty),)
        return replace(
            self,
            quantities=self.quantities.adjust(on_hand=-qty),
            reservations=remaining,
            version=self.version + 1,
        )

    def adjust_quantities(self, **deltas: Decimal) -> "StockPosition":
        """`AdjustStock` (`09_COMMAND_MODEL.md`): ajuste nomeado por bucket,
        auditado pela aplicação (evento `inventory.stock_adjusted` com
        `reason`+`actor` — este método só garante a aritmética)."""
        return replace(self, quantities=self.quantities.adjust(**deltas), version=self.version + 1)


@dataclass(frozen=True, slots=True)
class DemandRef:
    """VO — `05_DOMAIN_MODEL.md` §1.9."""

    kind: DemandKind
    ref: TypedId


@dataclass(frozen=True, slots=True)
class StockReservation:
    """Raiz de agregado própria — não aninhada em `StockPosition`
    (`06_AGGREGATE_ANALYSIS.md` §3). `05_DOMAIN_MODEL.md` §1.9."""

    reservation_id: TypedId
    organization_id: OrganizationId
    stock_position_ref: TypedId
    demand: DemandRef
    qty: Decimal
    purpose: StockPurpose
    priority: int
    state: ReservationState = ReservationState.HELD
    decision_ref: TypedId | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.reservation_id.entity_type != "stock_reservation":
            raise ValueError(
                "reservation_id deve ter entity_type 'stock_reservation', recebido "
                f"'{self.reservation_id.entity_type}'."
            )
        if self.stock_position_ref.entity_type != "stock_position":
            raise ValueError(
                "stock_position_ref deve ter entity_type 'stock_position', recebido "
                f"'{self.stock_position_ref.entity_type}'."
            )
        _require_non_negative(self.qty, field_name="qty")
        if self.qty == 0:
            raise ValueError("qty deve ser > 0.")
        if self.priority < 0:
            raise ValueError("priority não pode ser negativa.")

    def allocate(self) -> "StockReservation":
        if self.state is not ReservationState.HELD:
            raise TransicaoDeReservaInvalida(
                f"allocate só é válido a partir de HELD, estado atual '{self.state.value}'."
            )
        return replace(self, state=ReservationState.ALLOCATED, version=self.version + 1)

    def consume(self) -> "StockReservation":
        if self.state is not ReservationState.ALLOCATED:
            raise TransicaoDeReservaInvalida(
                f"consume só é válido a partir de ALLOCATED, estado atual '{self.state.value}'."
            )
        return replace(self, state=ReservationState.CONSUMED, version=self.version + 1)

    def release(self) -> "StockReservation":
        if self.state not in (ReservationState.HELD, ReservationState.ALLOCATED):
            raise TransicaoDeReservaInvalida(
                f"release só é válido a partir de HELD/ALLOCATED, estado atual "
                f"'{self.state.value}'."
            )
        return replace(self, state=ReservationState.RELEASED, version=self.version + 1)

    def to_line(self) -> StockReservationLine:
        """Projeção para `StockPosition.reservations` (`06_AGGREGATE_ANALYSIS.md` §3)."""
        return StockReservationLine(
            reservation_id=self.reservation_id,
            demand_ref=self.demand.ref,
            qty=self.qty,
            priority=self.priority,
            purpose_lock=self.purpose,
        )


@dataclass(frozen=True, slots=True)
class StockTransfer:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §1.10; I‑INV‑4 (cenário B)."""

    transfer_id: TypedId
    organization_id: OrganizationId
    part_ref: TypedId
    from_location_ref: TypedId
    to_location_ref: TypedId
    qty: Decimal
    state: TransferState = TransferState.REQUESTED
    qty_received: Decimal = Decimal(0)
    linked_reservation_ref: TypedId | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.transfer_id.entity_type != "stock_transfer":
            raise ValueError(
                "transfer_id deve ter entity_type 'stock_transfer', recebido "
                f"'{self.transfer_id.entity_type}'."
            )
        if self.from_location_ref == self.to_location_ref:
            raise ValueError(
                "from_location_ref e to_location_ref não podem ser a mesma localização."
            )
        _require_non_negative(self.qty, field_name="qty")
        if self.qty == 0:
            raise ValueError("qty deve ser > 0.")
        _require_non_negative(self.qty_received, field_name="qty_received")
        if self.qty_received > self.qty:
            raise RecebimentoExcedeDespacho(
                f"qty_received ({self.qty_received}) excede qty despachada ({self.qty})."
            )

    def dispatch(self) -> "StockTransfer":
        if self.state is not TransferState.REQUESTED:
            raise TransicaoDeTransferenciaInvalida(
                f"dispatch só é válido a partir de REQUESTED, estado atual '{self.state.value}'."
            )
        return replace(self, state=TransferState.IN_TRANSIT, version=self.version + 1)

    def receive(self, qty_this_receipt: Decimal) -> "StockTransfer":
        """I‑INV‑4: `Σ recebido ≤ qty despachada`; pode ser parcial."""
        if self.state not in (TransferState.IN_TRANSIT, TransferState.PARTIALLY_RECEIVED):
            raise TransicaoDeTransferenciaInvalida(
                "receive só é válido a partir de IN_TRANSIT/PARTIALLY_RECEIVED, estado atual "
                f"'{self.state.value}'."
            )
        if qty_this_receipt <= 0:
            raise ValueError("qty_this_receipt deve ser > 0.")
        new_received = self.qty_received + qty_this_receipt
        if new_received > self.qty:
            raise RecebimentoExcedeDespacho(
                f"Recebimento total ({new_received}) excederia o despachado ({self.qty})."
            )
        new_state = (
            TransferState.RECEIVED if new_received == self.qty else TransferState.PARTIALLY_RECEIVED
        )
        return replace(self, qty_received=new_received, state=new_state, version=self.version + 1)
