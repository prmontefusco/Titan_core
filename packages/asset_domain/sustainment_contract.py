"""Agregado `SLIContract` — Titan Asset & Sustainment (A2, módulo `sustainment`).

Decisão B1 (`docs/asset/adr/draft-20260910-primeiro-slice-titan-asset-sustainment.md`):
`sustainment` é a mesma vertical de `asset` (`vertical_id = asset`); este módulo
pode importar `packages.asset_domain` (já é o mesmo pacote Python). A fronteira
externa que vale é `asset` ⊥ `livestock`.

Modelo: `docs/asset/05_DOMAIN_MODEL.md` §2.1‑2.2. Invariantes
(`docs/asset/07_INVARIANTS.md`): I‑SLI‑1 (uma linha de contrato ativa por
serviço, resolvida por tempo — a seleção de versão em si), I‑SLI‑2 (seleção
temporal precede qualquer avaliação de cobertura — `resolve_version_at` é
exatamente essa seleção, isolada de qualquer `Rule`), I‑SLI‑3 (`ContractVersion`
imutável após emissão — garantido estruturalmente: `versions` só cresce por
`issue_version`, nenhum método edita uma versão existente), I‑SLI‑5 (entitlement
não excede cobertura — `ServiceLimits` aqui só guarda o teto; o consumo
acumulado é fato da aplicação) e I‑SLI‑6 (cobertura de contratos concorrentes
não ambígua — cross‑agregado, mesmo padrão de `configuration.py`
`require_no_overlapping_effectivity`).

**Entitlement não é modelado aqui.** É o resultado de uma `Evaluation → Decision`
do Core (`05_DOMAIN_MODEL.md` §2.3) — este módulo só monta os fatos que a
aplicação submete à `Rule` governada; não há classe `Entitlement` de verdade
própria da vertical (I‑SLI‑4).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class ContractScope(StrEnum):
    MODEL = "MODEL"
    VEHICLE = "VEHICLE"
    SITE = "SITE"
    REGION = "REGION"


class CoberturaAmbigua(ValueError):
    """Duas linhas de cobertura, do mesmo ou de contratos diferentes, cobrem o
    mesmo escopo no mesmo instante sem base determinística de escolha (I‑SLI‑6)."""


class VersaoDeContratoInvalida(ValueError):
    """`issue_version` chamado com `version_no` fora de sequência (I‑SLI‑3)."""


@dataclass(frozen=True, slots=True)
class KnownValidInterval:
    """VO — tempo válido (vigência) + tempo de conhecimento
    (`shared_kernel.temporal`; I‑SLI‑2)."""

    valid_from: datetime
    known_at: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        require_utc(self.valid_from, field_name="valid_from")
        require_utc(self.known_at, field_name="known_at")
        if self.valid_until is not None:
            require_utc(self.valid_until, field_name="valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until deve ser posterior a valid_from.")

    def covers(self, instant: datetime) -> bool:
        if instant < self.valid_from:
            return False
        return self.valid_until is None or instant < self.valid_until


@dataclass(frozen=True, slots=True)
class CoverageLine:
    """VO — `05_DOMAIN_MODEL.md` §2.2."""

    scope: ContractScope
    scope_value: str
    covered_services: tuple[str, ...] = ()
    covered_parts: tuple[TypedId, ...] = ()
    excluded_parts: tuple[TypedId, ...] = ()
    labor_rules: str | None = None
    travel_rules: str | None = None

    def __post_init__(self) -> None:
        if not self.scope_value or not self.scope_value.strip():
            raise ValueError("scope_value não pode ser vazio.")
        overlap = set(self.covered_parts) & set(self.excluded_parts)
        if overlap:
            raise ValueError(
                f"Peça(s) {sorted(p.value for p in overlap)} não pode(m) estar em "
                "covered_parts e excluded_parts ao mesmo tempo."
            )

    def covers_part(self, part_ref: TypedId) -> bool:
        if part_ref in self.excluded_parts:
            return False
        return not self.covered_parts or part_ref in self.covered_parts


@dataclass(frozen=True, slots=True)
class SLA:
    """VO — `05_DOMAIN_MODEL.md` §2.2."""

    duration: timedelta
    clock_start_event: str
    clock_stop_event: str
    pause_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.duration <= timedelta(0):
            raise ValueError("duration deve ser positiva.")
        if not self.clock_start_event or not self.clock_start_event.strip():
            raise ValueError("clock_start_event não pode ser vazio.")
        if not self.clock_stop_event or not self.clock_stop_event.strip():
            raise ValueError("clock_stop_event não pode ser vazio.")


@dataclass(frozen=True, slots=True)
class ServiceLimits:
    """VO — tetos por período (`05_DOMAIN_MODEL.md` §2.2). O consumo
    acumulado contra este teto é fato da aplicação (I‑SLI‑5); esta classe só
    guarda a regra."""

    max_services_per_period: int
    period_days: int

    def __post_init__(self) -> None:
        if self.max_services_per_period < 1:
            raise ValueError("max_services_per_period deve ser >= 1.")
        if self.period_days < 1:
            raise ValueError("period_days deve ser >= 1.")


@dataclass(frozen=True, slots=True)
class ContractVersion:
    """Entidade interna de `SLIContract`, append‑only (I‑SLI‑3)."""

    version_no: int
    effective: KnownValidInterval
    coverage_lines: tuple[CoverageLine, ...] = ()
    response_sla: SLA | None = None
    repair_sla: SLA | None = None
    availability_target_percentage: Decimal | None = None
    service_limits: ServiceLimits | None = None
    amendment_ref: TypedId | None = None

    def __post_init__(self) -> None:
        if isinstance(self.version_no, bool) or not isinstance(self.version_no, int):
            raise TypeError("version_no deve ser inteiro.")
        if self.version_no < 1:
            raise ValueError("version_no deve ser >= 1.")
        if self.availability_target_percentage is not None and not (
            0 <= self.availability_target_percentage <= 100
        ):
            raise ValueError("availability_target_percentage deve estar entre 0 e 100.")
        if (
            self.amendment_ref is not None
            and self.amendment_ref.entity_type != "contract_amendment"
        ):
            raise ValueError(
                "amendment_ref deve ter entity_type 'contract_amendment', recebido "
                f"'{self.amendment_ref.entity_type}'."
            )

    def coverage_for(self, *, scope: ContractScope, scope_value: str) -> CoverageLine | None:
        for line in self.coverage_lines:
            if line.scope is scope and line.scope_value == scope_value:
                return line
        return None


@dataclass(frozen=True, slots=True)
class SLIContract:
    """Raiz de agregado. `05_DOMAIN_MODEL.md` §2.1; I‑SLI‑1, I‑SLI‑2, I‑SLI‑3."""

    contract_id: TypedId
    organization_id: OrganizationId
    customer_ref: TypedId
    versions: tuple[ContractVersion, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        if self.contract_id.entity_type != "sli_contract":
            raise ValueError(
                "contract_id deve ter entity_type 'sli_contract', recebido "
                f"'{self.contract_id.entity_type}'."
            )
        if self.customer_ref.entity_type != "customer":
            raise ValueError(
                "customer_ref deve ter entity_type 'customer', recebido "
                f"'{self.customer_ref.entity_type}'."
            )
        numbers = [v.version_no for v in self.versions]
        if numbers != list(range(1, len(numbers) + 1)):
            raise VersaoDeContratoInvalida(
                f"version_no das ContractVersion devem ser 1..N sem lacuna nem repetição, "
                f"recebido {numbers}."
            )

    @property
    def current_version_no(self) -> int | None:
        return self.versions[-1].version_no if self.versions else None

    def issue_version(self, version: ContractVersion) -> "SLIContract":
        """`IssueContractVersion`/`AmendContract` (`09_COMMAND_MODEL.md`).
        `version_no` deve ser exatamente o próximo — nunca reescreve uma versão
        existente (I‑SLI‑3)."""
        expected = len(self.versions) + 1
        if version.version_no != expected:
            raise VersaoDeContratoInvalida(
                f"Próxima versão deve ser {expected}, recebido {version.version_no}."
            )
        if self.versions and version.effective.valid_from < self.versions[-1].effective.valid_from:
            raise ValueError(
                "valid_from da nova versão não pode retroceder em relação à versão anterior."
            )
        return replace(self, versions=self.versions + (version,), version=self.version + 1)

    def resolve_version_at(
        self, instant: datetime, *, known_at: datetime | None = None
    ) -> ContractVersion | None:
        """I‑SLI‑1/2: seleção temporal isolada de qualquer regra de cobertura.
        Entre as versões cujo `valid_from` já havia começado em `instant` (e,
        se `known_at` informado, cujo `known_at` também já era conhecido
        naquele momento), devolve a de maior `version_no` — a mais recente que
        já valia. Determinístico por construção: no máximo uma tem o maior
        `version_no` dentre as candidatas.
        """
        require_utc(instant, field_name="instant")
        candidates = [v for v in self.versions if v.effective.valid_from <= instant]
        if known_at is not None:
            require_utc(known_at, field_name="known_at")
            candidates = [v for v in candidates if v.effective.known_at <= known_at]
        if not candidates:
            return None
        return max(candidates, key=lambda v: v.version_no)


@dataclass(frozen=True, slots=True)
class ResolvedCoverage:
    """Par (contrato, versão já resolvida por `resolve_version_at`) — o insumo
    de `require_unambiguous_coverage`. A aplicação monta um destes para o
    contrato candidato e um por concorrente, ambos resolvidos para o mesmo
    instante, antes de checar a ambiguidade."""

    contract: SLIContract
    version: ContractVersion


def require_unambiguous_coverage(
    candidate: ResolvedCoverage, others: Sequence[ResolvedCoverage], *, at: datetime
) -> None:
    """I‑SLI‑6. `others` são as demais `SLIContract` (já resolvidas para o
    instante `at`) da mesma Organization que a aplicação buscou no
    repositório. Recusa se duas linhas de cobertura de contratos **diferentes**
    cobrirem o mesmo `(scope, scope_value)` no mesmo instante — sem isso,
    `OpenWorkOrder`/`ResolveEntitlement` não teriam base determinística para
    escolher entre elas."""
    candidate_keys = {(line.scope, line.scope_value) for line in candidate.version.coverage_lines}
    if not candidate_keys:
        return
    for other in others:
        if other.contract.contract_id == candidate.contract.contract_id:
            continue
        other_keys = {(line.scope, line.scope_value) for line in other.version.coverage_lines}
        shared = candidate_keys & other_keys
        if shared:
            raise CoberturaAmbigua(
                f"Contratos '{candidate.contract.contract_id.value}' e "
                f"'{other.contract.contract_id.value}' cobrem ambos {sorted(shared)} em "
                f"{at.isoformat()}."
            )
