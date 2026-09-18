"""PostgreSQL composition for Commercial Passport dynamic projections.

This adapter reads only owner-scoped Livestock/Core material already protected by
the request transaction RLS context. It does not evaluate Policy, emit Decision,
persist reports, issue Dossiers or authorize external disclosure.
"""

from dataclasses import dataclass

from sqlalchemy import Connection, and_, exists, select

from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.livestock_application.commercial_passport import (
    CommercialOpportunity,
    CommercialPassport,
    CommercialPassportContext,
    CommercialPassportMarketReadinessSource,
    PropertyCommercialPassportMarketReadinessPipeline,
    PropertyCommercialPassportProjectionPort,
)
from packages.livestock_application.market_readiness import (
    MarketReadinessContext,
    MarketReadinessPopulationReader,
    MarketReadinessService,
)
from packages.livestock_domain.animal import BirthOutcome
from packages.livestock_infrastructure.persistence.animal_repository import animals_table
from packages.livestock_infrastructure.persistence.exit_repository import animal_exits_table
from packages.shared_kernel import TypedId


@dataclass(frozen=True, slots=True)
class TransactionalPropertyCommercialPassportReadinessPipeline(
    PropertyCommercialPassportProjectionPort,
):
    """Build a Property Commercial Passport from persisted MarketReadiness inputs."""

    connection: Connection
    opportunity: CommercialOpportunity
    readiness_service: MarketReadinessService = MarketReadinessService()

    def build_property_passport(
        self,
        *,
        context: CommercialPassportContext,
    ) -> CommercialPassport:
        report = MarketReadinessPopulationReader(
            decision_repository=TransactionalDecisionRepository(self.connection),
            evaluation_repository=TransactionalEvaluationRepository(self.connection),
            readiness_service=self.readiness_service,
        ).build_for_animals(
            context=MarketReadinessContext(
                organization_id=context.organization_id,
                purpose=self.opportunity.purpose,
                policy_id=self.opportunity.policy_id,
                policy_version=self.opportunity.policy_version,
                reference_time=context.reference_time,
                knowledge_cutoff=context.knowledge_cutoff,
            ),
            animal_ids=self._active_animals_for_property(context),
        )
        return PropertyCommercialPassportMarketReadinessPipeline(
            sources=(
                CommercialPassportMarketReadinessSource(
                    opportunity=self.opportunity,
                    report=report,
                    limitations=("population resolved from active animals born at property",),
                ),
            ),
        ).build_property_passport(context=context)

    def _active_animals_for_property(
        self,
        context: CommercialPassportContext,
    ) -> tuple[TypedId, ...]:
        rows = self.connection.execute(
            select(animals_table.c.animal_id)
            .where(
                animals_table.c.record_owner_organization_id == context.organization_id.value,
                animals_table.c.birth_property_id == context.property_id.value,
                animals_table.c.birth_outcome != BirthOutcome.NATIMORTO.value,
                ~exists(
                    select(animal_exits_table.c.exit_id).where(
                        and_(
                            animal_exits_table.c.animal_id == animals_table.c.animal_id,
                            animal_exits_table.c.occurred_at <= context.reference_time,
                        ),
                    ),
                ),
            )
            .order_by(animals_table.c.animal_id.asc()),
        ).fetchall()
        return tuple(TypedId("animal", row.animal_id) for row in rows)
