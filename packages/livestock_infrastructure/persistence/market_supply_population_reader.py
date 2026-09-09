"""Owner-scoped PostgreSQL reader for Market Supply candidate animal subjects.

The reader runs only inside the record owner's RLS context. It produces minimal
candidate subject descriptors for the application resolver; it does not decide
readiness, eligibility, disclosure or cross-tenant access.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import Connection, and_, exists, select, text

from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.organizations import set_local_organization_context
from packages.livestock_application.market_readiness import (
    MarketReadinessContext,
    MarketReadinessPopulationReader,
    MarketReadinessReport,
    MarketReadinessService,
)
from packages.livestock_application.market_supply_population import (
    CandidatePopulationCriteria,
    CandidatePopulationSnapshot,
    CandidatePopulationSubject,
)
from packages.livestock_domain.animal import BirthOutcome
from packages.livestock_infrastructure.persistence.animal_repository import animals_table
from packages.livestock_infrastructure.persistence.exit_repository import animal_exits_table
from packages.shared_kernel import OrganizationId, TypedId


@dataclass(frozen=True, slots=True)
class TransactionalOwnerScopedCandidateAnimalReader:
    """Reads candidate animals visible under the active owner Organization RLS."""

    connection: Connection

    def list_subjects(
        self,
        *,
        criteria: CandidatePopulationCriteria,
    ) -> tuple[CandidatePopulationSubject, ...]:
        if criteria.subject_type != "animal":
            raise ValueError("TransactionalOwnerScopedCandidateAnimalReader suporta apenas animal.")
        self._assert_owner_context(criteria.organization_id)

        stmt = (
            select(
                animals_table.c.animal_id,
                animals_table.c.record_owner_organization_id,
                animals_table.c.birth_property_id,
                animals_table.c.created_at,
            )
            .where(
                animals_table.c.record_owner_organization_id == criteria.organization_id.value,
                animals_table.c.birth_outcome != BirthOutcome.NATIMORTO.value,
                ~exists(
                    select(animal_exits_table.c.exit_id).where(
                        and_(
                            animal_exits_table.c.animal_id == animals_table.c.animal_id,
                            animal_exits_table.c.occurred_at <= criteria.reference_time,
                        )
                    )
                ),
            )
            .order_by(animals_table.c.animal_id.asc())
        )
        rows = self.connection.execute(stmt).fetchall()
        subjects: list[CandidatePopulationSubject] = []
        for row in rows:
            known_at = row.created_at
            if known_at.tzinfo is None:
                known_at = known_at.replace(tzinfo=UTC)
            subjects.append(
                CandidatePopulationSubject(
                    subject_id=TypedId("animal", row.animal_id),
                    organization_id=OrganizationId(row.record_owner_organization_id),
                    property_id=(
                        None
                        if row.birth_property_id is None
                        else TypedId("rural_property", row.birth_property_id)
                    ),
                    known_at=known_at,
                )
            )
        return tuple(subjects)

    def _assert_owner_context(self, organization_id: OrganizationId) -> None:
        if not self.connection.in_transaction():
            raise RuntimeError("Market Supply candidate reader exige transacao ativa.")
        current_organization_id = self.connection.execute(
            text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
        ).scalar_one_or_none()
        if str(current_organization_id) != str(organization_id.value):
            raise RuntimeError(
                "Market Supply candidate reader exige contexto RLS do owner Organization."
            )


@dataclass(frozen=True, slots=True)
class TransactionalMarketSupplyOwnerScopedSubjectReader:
    """Application-mediated owner-scoped subject reader for Market Supply F3.5.

    The buyer request may start under the buyer Organization context. Each
    contribution read is temporarily scoped to the grant owner and the previous
    context is restored before returning to the caller.
    """

    connection: Connection
    owner_connection_factory: Callable[[], AbstractContextManager[Connection]] | None = None

    def list_subjects(
        self,
        *,
        criteria: CandidatePopulationCriteria,
    ) -> tuple[CandidatePopulationSubject, ...]:
        if self.owner_connection_factory is not None:
            with self.owner_connection_factory() as owner_connection, owner_connection.begin():
                set_local_organization_context(owner_connection, criteria.organization_id)
                return TransactionalOwnerScopedCandidateAnimalReader(
                    owner_connection,
                ).list_subjects(criteria=criteria)

        previous_organization_id = self._current_organization_id()
        set_local_organization_context(self.connection, criteria.organization_id)
        try:
            return TransactionalOwnerScopedCandidateAnimalReader(self.connection).list_subjects(
                criteria=criteria,
            )
        finally:
            self._restore_organization_context(previous_organization_id)

    def _current_organization_id(self) -> OrganizationId | None:
        raw = self.connection.execute(
            text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
        ).scalar_one_or_none()
        if raw is None:
            return None
        return OrganizationId(raw)

    def _restore_organization_context(self, organization_id: OrganizationId | None) -> None:
        if organization_id is None:
            self.connection.execute(
                text("SELECT set_config('titan.organization_id', '', true)"),
            )
            return
        set_local_organization_context(self.connection, organization_id)


@dataclass(frozen=True, slots=True)
class TransactionalMarketSupplyOwnerScopedReadinessExecutor:
    """Runs MarketReadiness repository reads under the contributor's RLS context."""

    connection: Connection

    def run_for_owner(
        self,
        *,
        organization_id: OrganizationId,
        callback: Callable[[], MarketReadinessReport],
    ) -> MarketReadinessReport:
        previous_organization_id = self._current_organization_id()
        set_local_organization_context(self.connection, organization_id)
        try:
            return callback()
        finally:
            self._restore_organization_context(previous_organization_id)

    def _current_organization_id(self) -> OrganizationId | None:
        raw = self.connection.execute(
            text("SELECT NULLIF(current_setting('titan.organization_id', true), '')::uuid"),
        ).scalar_one_or_none()
        if raw is None:
            return None
        return OrganizationId(raw)

    def _restore_organization_context(self, organization_id: OrganizationId | None) -> None:
        if organization_id is None:
            self.connection.execute(
                text("SELECT set_config('titan.organization_id', '', true)"),
            )
            return
        set_local_organization_context(self.connection, organization_id)


@dataclass(frozen=True, slots=True)
class TransactionalMarketSupplyOwnerScopedReadinessReportBuilder:
    """Builds MarketReadiness reports on a dedicated contributor connection."""

    owner_connection_factory: Callable[[], AbstractContextManager[Connection]]
    readiness_service: MarketReadinessService

    def build_report_for_snapshot(
        self,
        *,
        snapshot: CandidatePopulationSnapshot,
    ) -> MarketReadinessReport:
        with self.owner_connection_factory() as owner_connection, owner_connection.begin():
            set_local_organization_context(owner_connection, snapshot.criteria.organization_id)
            criteria = snapshot.criteria
            return MarketReadinessPopulationReader(
                decision_repository=TransactionalDecisionRepository(owner_connection),
                evaluation_repository=TransactionalEvaluationRepository(owner_connection),
                readiness_service=self.readiness_service,
            ).build_for_animals(
                context=MarketReadinessContext(
                    organization_id=criteria.organization_id,
                    purpose=criteria.purpose,
                    policy_id=criteria.policy_id,
                    policy_version=criteria.policy_version,
                    reference_time=criteria.reference_time,
                    knowledge_cutoff=criteria.knowledge_cutoff,
                ),
                animal_ids=snapshot.included_subject_ids,
            )
