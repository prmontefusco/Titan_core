"""Testes do serviço de importação de asserções de qualificação (ADR-0045)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.evidence import ConfidenceTier
from packages.livestock_application.event_recorder import LivestockOperationContext
from packages.livestock_application.qualification_assertion_import_service import (
    QualificationAssertionImportService,
    QualificationAssertionInput,
    compute_confidence,
)
from packages.livestock_domain.establishment_qualification_assertion import (
    AssertionStatus,
    EstablishmentQualificationAssertion,
)
from packages.livestock_domain.external_counterparty import (
    CounterpartyType,
    ExternalCounterparty,
)
from packages.livestock_domain.qualification_source_artifact import (
    QualificationSourceArtifact,
    SourceCoverage,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


class FakeArtifactRepository:
    def __init__(self) -> None:
        self.store: dict[object, QualificationSourceArtifact] = {}

    def save(self, artifact: QualificationSourceArtifact) -> None:
        self.store[artifact.artifact_id.value] = artifact

    def find_by_identity(
        self, organization_id: OrganizationId, source: str, source_version: str
    ) -> QualificationSourceArtifact | None:
        for artifact in self.store.values():
            if (
                artifact.organization_id == organization_id
                and artifact.source == source
                and artifact.source_version == source_version
            ):
                return artifact
        return None

    def find_latest_complete_snapshot(
        self, organization_id: OrganizationId, source: str
    ) -> QualificationSourceArtifact | None:
        candidates = [
            a
            for a in self.store.values()
            if a.organization_id == organization_id
            and a.source == source
            and a.snapshot_semantics == SourceCoverage.COMPLETE_SNAPSHOT
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda a: a.observed_at)


class FakeAssertionRepository:
    def __init__(self) -> None:
        self.store: list[EstablishmentQualificationAssertion] = []

    def save(self, assertion: EstablishmentQualificationAssertion) -> None:
        self.store.append(assertion)

    def list_by_establishment(
        self, organization_id: OrganizationId, establishment_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]:
        return [
            a
            for a in self.store
            if a.organization_id == organization_id and a.establishment_id == establishment_id
        ]

    def list_by_source_artifact(
        self, organization_id: OrganizationId, source_artifact_id: TypedId
    ) -> list[EstablishmentQualificationAssertion]:
        return [
            a
            for a in self.store
            if a.organization_id == organization_id and a.source_artifact_id == source_artifact_id
        ]


class FakeCounterpartyRepository:
    def __init__(self, counterparties: Iterable[ExternalCounterparty]) -> None:
        self.counterparties = {c.counterparty_id.value: c for c in counterparties}

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        return self.counterparties.get(counterparty_id.value)

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.counterparties[counterparty.counterparty_id.value] = counterparty

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return [c for c in self.counterparties.values() if c.organization_id == organization_id]


@dataclass
class Ambiente:
    service: QualificationAssertionImportService
    artifact_repo: FakeArtifactRepository
    assertion_repo: FakeAssertionRepository
    counterparty_repo: FakeCounterpartyRepository


def _org() -> OrganizationId:
    return OrganizationId(uuid4())


def _context(org_id: OrganizationId, actor_entity_type: str = "user") -> LivestockOperationContext:
    actor_id = TypedId.new(actor_entity_type)
    return LivestockOperationContext(
        organization_id=org_id,
        actor_reference=UniversalReference(
            target_id=actor_id, organization_id=org_id, contract_version=1
        ),
        source_reference=UniversalReference(
            target_id=TypedId.new("system"), organization_id=org_id, contract_version=1
        ),
        correlation_id=TypedId.new("correlation"),
    )


def _establishment(org_id: OrganizationId) -> ExternalCounterparty:
    return ExternalCounterparty(
        counterparty_id=TypedId.new("external_counterparty"),
        organization_id=org_id,
        name="Frigorifico Teste",
        counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
    )


def _ambiente() -> Ambiente:
    artifact_repo = FakeArtifactRepository()
    assertion_repo = FakeAssertionRepository()
    counterparty_repo = FakeCounterpartyRepository([])
    service = QualificationAssertionImportService(
        artifact_repository=artifact_repo,
        assertion_repository=assertion_repo,
        counterparty_repository=counterparty_repo,
    )
    return Ambiente(
        service=service,
        artifact_repo=artifact_repo,
        assertion_repo=assertion_repo,
        counterparty_repo=counterparty_repo,
    )


# -- Importação básica --------------------------------------------------------


def test_importacao_cria_source_artifact_e_assertions() -> None:
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    resultado = ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="2026-07-27T00:00Z",
        content_hash="sha256:aaa",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    assert not resultado.already_imported
    assert resultado.created_assertions == 1
    assert resultado.inferred_absence_assertions == 0
    assert len(ambiente.assertion_repo.store) == 1
    assert ambiente.assertion_repo.store[0].asserted_status == AssertionStatus.QUALIFIED


def test_estabelecimento_de_outra_organizacao_e_rejeitado() -> None:
    org_id = _org()
    ambiente = _ambiente()
    outra_org = _org()
    estab = _establishment(outra_org)
    ambiente.counterparty_repo.save(estab)

    with pytest.raises(KeyError):
        ambiente.service.import_assertions(
            context=_context(org_id),
            source="MAPA",
            source_version="v1",
            content_hash="sha256:aaa",
            snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
            observed_at=datetime(2026, 7, 27, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=estab.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.QUALIFIED,
                )
            ],
        )


# -- Idempotência (teste 2 da seção 11) ---------------------------------------


def test_reimportacao_da_mesma_versao_nao_duplica() -> None:
    """Mesma source_version importada 2x não duplica."""
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    entrada = [
        QualificationAssertionInput(
            establishment_id=estab.counterparty_id,
            qualification_type="EXPORT_CN",
            asserted_status=AssertionStatus.QUALIFIED,
        )
    ]

    r1 = ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v1",
        content_hash="sha256:aaa",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=entrada,
    )
    assert not r1.already_imported
    assert len(ambiente.assertion_repo.store) == 1

    r2 = ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v1",
        content_hash="sha256:aaa",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=entrada,
    )
    assert r2.already_imported
    assert r2.source_artifact_id == r1.source_artifact_id
    assert len(ambiente.assertion_repo.store) == 1  # nao duplicou


def test_mesma_source_version_com_content_hash_diferente_e_rejeitada() -> None:
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    entrada = [
        QualificationAssertionInput(
            establishment_id=estab.counterparty_id,
            qualification_type="EXPORT_CN",
            asserted_status=AssertionStatus.QUALIFIED,
        )
    ]

    ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v1",
        content_hash="sha256:aaa",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=entrada,
    )

    with pytest.raises(ValueError, match="content_hash diferente"):
        ambiente.service.import_assertions(
            context=context,
            source="MAPA",
            source_version="v1",
            content_hash="sha256:bbb",
            snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
            observed_at=datetime(2026, 7, 27, tzinfo=UTC),
            assertions=entrada,
        )


# -- Reconciliação com cobertura (testes 3 e 4 da seção 11) -------------------


def test_ausencia_em_complete_snapshot_produz_unknown_nunca_not_qualified() -> None:
    """COMPLETE_SNAPSHOT -> UNKNOWN, nunca NOT_QUALIFIED."""
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    # Versao 1: estabelecimento QUALIFIED
    ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="2026-03-15T00:00Z",
        content_hash="sha256:v1",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 3, 15, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    # Versao 2: estabelecimento desapareceu da lista completa
    outro_estab = _establishment(org_id)
    ambiente.counterparty_repo.save(outro_estab)
    resultado = ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="2026-07-27T00:00Z",
        content_hash="sha256:v2",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=outro_estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    assert resultado.inferred_absence_assertions == 1

    derivadas = [
        a
        for a in ambiente.assertion_repo.store
        if a.establishment_id == estab.counterparty_id
        and a.source_artifact_id == resultado.source_artifact_id
    ]
    assert len(derivadas) == 1
    # UNKNOWN, nunca NOT_QUALIFIED: ausência não decide, apenas registra.
    assert derivadas[0].asserted_status == AssertionStatus.UNKNOWN
    # Honestidade temporal: nao inventa datas
    assert derivadas[0].effective_from is None
    assert derivadas[0].effective_until is None


def test_ausencia_em_partial_nao_gera_assertion_derivada() -> None:
    """Snapshot PARTIAL não gera Assertion de ausência."""
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v1-complete",
        content_hash="sha256:v1",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 3, 15, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    outro_estab = _establishment(org_id)
    ambiente.counterparty_repo.save(outro_estab)
    resultado = ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v2-partial",
        content_hash="sha256:v2",
        snapshot_semantics=SourceCoverage.PARTIAL,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=outro_estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    # Nenhuma inferencia de ausencia a partir de PARTIAL
    assert resultado.inferred_absence_assertions == 0
    derivadas = [
        a
        for a in ambiente.assertion_repo.store
        if a.establishment_id == estab.counterparty_id
        and a.source_artifact_id == resultado.source_artifact_id
    ]
    assert len(derivadas) == 0


# -- Conhecimento histórico vs retrospectivo (teste 5 da seção 11) -----------


def test_conhecimento_posterior_nao_altera_reproducao_historica() -> None:
    """Conhecimento posterior não reescreve decisão histórica.

    Uma Decision tomada com cutoff T1 permanece reproduzível com Assertions
    de observed_at <= T1, mesmo após nova Assertion (observed_at > T1)
    revelar effective_from anterior a T1.
    """
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)
    context = _context(org_id)

    cutoff_da_decisao = datetime(2026, 7, 20, tzinfo=UTC)

    ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v1",
        content_hash="sha256:v1",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.QUALIFIED,
            )
        ],
    )

    # Reproducao da decisao de 20/07: so Assertions com observed_at <= cutoff
    conhecidas_em_20_07 = [
        a
        for a in ambiente.assertion_repo.list_by_establishment(org_id, estab.counterparty_id)
        if a.known_as_of(cutoff_da_decisao)
    ]
    assert len(conhecidas_em_20_07) == 1
    assert conhecidas_em_20_07[0].asserted_status == AssertionStatus.QUALIFIED

    # Conhecimento posterior (27/07): revela que a habilitacao terminou em 10/07
    ambiente.service.import_assertions(
        context=context,
        source="MAPA",
        source_version="v2",
        content_hash="sha256:v2",
        snapshot_semantics=SourceCoverage.DELTA,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=[
            QualificationAssertionInput(
                establishment_id=estab.counterparty_id,
                qualification_type="EXPORT_CN",
                asserted_status=AssertionStatus.NOT_QUALIFIED,
                effective_from=datetime(2026, 7, 10, tzinfo=UTC),
            )
        ],
    )

    # A reproducao com o MESMO cutoff de 20/07 continua identica:
    # a nova Assertion tem observed_at=27/07, posterior ao cutoff.
    conhecidas_em_20_07_apos_novo_conhecimento = [
        a
        for a in ambiente.assertion_repo.list_by_establishment(org_id, estab.counterparty_id)
        if a.known_as_of(cutoff_da_decisao)
    ]
    assert conhecidas_em_20_07_apos_novo_conhecimento == conhecidas_em_20_07

    # Auditoria retrospectiva hoje: descobre que em 15/07 (embarque) a
    # habilitacao ja nao era valida, embora nao pudessemos saber em 20/07.
    todas = ambiente.assertion_repo.list_by_establishment(org_id, estab.counterparty_id)
    cobrindo_embarque = [a for a in todas if a.effective_at(datetime(2026, 7, 15, tzinfo=UTC))]
    assert len(cobrindo_embarque) == 1
    assert cobrindo_embarque[0].asserted_status == AssertionStatus.NOT_QUALIFIED


# -- Confiança computada pelo Titan (teste 6 da seção 11) --------------------


def test_confidence_nunca_vem_do_payload_e_e_computada() -> None:
    """confidence nunca é aceito do payload HTTP; é sempre computado."""
    org_id = _org()
    ambiente = _ambiente()
    estab = _establishment(org_id)
    ambiente.counterparty_repo.save(estab)

    # QualificationAssertionInput nao possui campo confidence -- e
    # impossivel para o chamador declarar um nivel arbitrario.
    entrada = QualificationAssertionInput(
        establishment_id=estab.counterparty_id,
        qualification_type="EXPORT_CN",
        asserted_status=AssertionStatus.QUALIFIED,
    )
    assert not hasattr(entrada, "confidence")
    assert not hasattr(entrada, "confidence_tier")

    ambiente.service.import_assertions(
        context=_context(org_id, actor_entity_type="user"),
        source="MAPA",
        source_version="v1",
        content_hash="sha256:v1",
        snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
        observed_at=datetime(2026, 7, 27, tzinfo=UTC),
        assertions=[entrada],
    )

    assert ambiente.assertion_repo.store[0].confidence_tier == ConfidenceTier.DOCUMENTED


def test_ator_do_tipo_system_produz_confianca_verificada() -> None:
    context = _context(_org(), actor_entity_type="system")
    assert compute_confidence(context=context) == ConfidenceTier.VERIFIED_SOURCE


def test_ator_humano_produz_documented() -> None:
    context = _context(_org(), actor_entity_type="user")
    assert compute_confidence(context=context) == ConfidenceTier.DOCUMENTED


def test_assinatura_verificada_produz_nivel_mais_alto() -> None:
    context = _context(_org(), actor_entity_type="user")
    assert (
        compute_confidence(context=context, has_verified_signature=True)
        == ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED
    )
