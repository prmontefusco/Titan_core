"""Asserção temporal sobre qualificação de estabelecimento (ADR-0045).

Distinta de `RuleAdoption` (ADR-0043): `RuleAdoption` é o ato de uma
Organization adotar uma regra normativa para uma finalidade. Esta classe é
o FATO que a regra consulta — "o estabelecimento X possui a qualificação Y,
segundo a fonte Z, observado em W" — e não carrega decisão alguma sobre o
que esse fato significa para uma finalidade de mercado.

Modelo bitemporal:
- `effective_from`/`effective_until` (valid time): quando a qualificação
  valia no mundo real, segundo a fonte. Só preenchido se a fonte afirma
  explicitamente essas datas — nunca inferido pela ausência em uma lista.
- `observed_at` (tempo declarado pela fonte) e `recorded_at` (knowledge/
  transaction time): quando a fonte observou e quando o Titan passou a
  conhecer a asserção. Ambos são sempre preenchidos e não são equivalentes.

Essa distinção permite duas perguntas diferentes:
- Reprodução histórica: "o que sabíamos quando decidimos?" → filtra por
  `recorded_at <= cutoff`.
- Auditoria retrospectiva: "o que sabemos hoje sobre aquele instante?" →
  filtra por `effective_from/until` cobrindo o instante em análise,
  independentemente de quando a asserção foi observada.

Conhecimento posterior nunca reescreve uma Decision já tomada; apenas
alimenta uma nova Evaluation, se solicitada.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from packages.core_domain.evidence import ConfidenceTier
from packages.shared_kernel import OrganizationId, TypedId
from packages.shared_kernel.temporal import require_utc


class AssertionStatus(StrEnum):
    """O que a fonte afirma sobre a qualificação.

    QUALIFIED: a fonte afirma positivamente a qualificação.

    NOT_QUALIFIED: a fonte afirma EXPLICITAMENTE que o estabelecimento não
    possui a qualificação (ex.: um código de status "REVOGADO" no próprio
    registro consultado). Ausência em uma lista nunca, por si só, produz
    NOT_QUALIFIED — isso seria o fato usurpando uma decisão que pertence
    à Policy.

    UNKNOWN: o material disponível não permite afirmar nenhum dos dois.
    Cobre tanto "desapareceu de um snapshot completo, sem explicação"
    quanto "recebemos relato sem fonte documental forte".
    """

    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EstablishmentQualificationAssertion:
    assertion_id: TypedId
    organization_id: OrganizationId
    establishment_id: TypedId
    qualification_type: str

    asserted_status: AssertionStatus
    effective_from: datetime | None
    effective_until: datetime | None

    observed_at: datetime
    source_artifact_id: TypedId
    confidence_tier: ConfidenceTier

    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_utc(self.observed_at, field_name="observed_at")
        require_utc(self.recorded_at, field_name="recorded_at")
        if self.effective_from is not None:
            require_utc(self.effective_from, field_name="effective_from")
        if self.effective_until is not None:
            require_utc(self.effective_until, field_name="effective_until")
        if (
            self.effective_from is not None
            and self.effective_until is not None
            and self.effective_from > self.effective_until
        ):
            raise ValueError("effective_from nao pode ser posterior a effective_until.")
        if self.assertion_id.entity_type != "establishment_qualification_assertion":
            raise ValueError(
                "assertion_id deve ter entity_type 'establishment_qualification_assertion'."
            )
        if self.establishment_id.entity_type != "external_counterparty":
            raise ValueError("establishment_id deve ter entity_type 'external_counterparty'.")
        if not self.qualification_type.strip():
            raise ValueError("qualification_type nao pode ser vazio.")
        if not isinstance(self.asserted_status, AssertionStatus):
            raise TypeError("asserted_status deve ser AssertionStatus.")
        if self.source_artifact_id.entity_type != "qualification_source_artifact":
            raise ValueError(
                "source_artifact_id deve ter entity_type 'qualification_source_artifact'. "
                "Toda Assertion precisa de um artefato de origem: fato sem "
                "proveniência declarada não existe."
            )
        if not isinstance(self.confidence_tier, ConfidenceTier):
            raise TypeError("confidence_tier deve ser ConfidenceTier.")

    @classmethod
    def create(
        cls,
        *,
        organization_id: OrganizationId,
        establishment_id: TypedId,
        qualification_type: str,
        asserted_status: AssertionStatus,
        effective_from: datetime | None,
        effective_until: datetime | None,
        observed_at: datetime,
        source_artifact_id: TypedId,
        confidence_tier: ConfidenceTier,
    ) -> "EstablishmentQualificationAssertion":
        return cls(
            assertion_id=TypedId.new("establishment_qualification_assertion"),
            organization_id=organization_id,
            establishment_id=establishment_id,
            qualification_type=qualification_type.strip(),
            asserted_status=asserted_status,
            effective_from=effective_from,
            effective_until=effective_until,
            observed_at=observed_at,
            source_artifact_id=source_artifact_id,
            confidence_tier=confidence_tier,
        )

    def known_as_of(self, cutoff: datetime) -> bool:
        """Reprodução histórica: esta asserção era conhecida no instante `cutoff`?"""
        require_utc(cutoff, field_name="cutoff")
        return self.recorded_at <= cutoff

    def effective_at(self, instant: datetime) -> bool:
        """Auditoria retrospectiva: esta asserção cobre o instante `instant`?

        Só responde com base em datas que a fonte declarou explicitamente.
        Quando `effective_from`/`effective_until` são desconhecidos, a
        asserção não afirma cobertura alguma sobre nenhum instante
        específico — cabe ao chamador tratar isso como lacuna.
        """
        require_utc(instant, field_name="instant")
        if self.effective_from is not None and instant < self.effective_from:
            return False
        if self.effective_until is not None and instant > self.effective_until:
            return False
        return self.effective_from is not None or self.effective_until is not None
