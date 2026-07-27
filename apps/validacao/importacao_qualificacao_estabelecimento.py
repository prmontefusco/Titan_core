"""Roteiro de validação para importação de asserções de qualificação (ADR-0045).

Diferente de um roteiro narrado com dados simulados, este roteiro chama o
`QualificationAssertionImportService` de verdade, em memória (sem banco),
usando os mesmos repositórios fake que os testes automatizados usam. O que é
impresso é o resultado real do serviço, não uma narrativa do que "deveria"
acontecer — a honestidade que a própria ADR-0045 exige do domínio se aplica
também à validação manual.

Marco 17.3a: importação e reconciliação de asserções de qualificação de
estabelecimento com fonte versionada, semântica de cobertura, e confiança
computada pelo Titan.

Execução: python -m apps.validacao.importacao_qualificacao_estabelecimento --pausar
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

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


class RepositorioArtefatosEmMemoria:
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
        candidatos = [
            a
            for a in self.store.values()
            if a.organization_id == organization_id
            and a.source == source
            and a.snapshot_semantics == SourceCoverage.COMPLETE_SNAPSHOT
        ]
        return max(candidatos, key=lambda a: a.observed_at) if candidatos else None


class RepositorioAssertionsEmMemoria:
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


class RepositorioContrapartesEmMemoria:
    def __init__(self) -> None:
        self.counterparties: dict[object, ExternalCounterparty] = {}

    def get_by_id(self, counterparty_id: TypedId) -> ExternalCounterparty | None:
        return self.counterparties.get(counterparty_id.value)

    def save(self, counterparty: ExternalCounterparty) -> None:
        self.counterparties[counterparty.counterparty_id.value] = counterparty

    def list_by_organization(self, organization_id: OrganizationId) -> list[ExternalCounterparty]:
        return [c for c in self.counterparties.values() if c.organization_id == organization_id]


def _linha(texto: str = "") -> None:
    print(texto)


def _cabecalho(titulo: str) -> None:
    _linha()
    _linha(f"### {titulo}")


@dataclass
class RoteiroImportacaoQualificacao:
    """Roda o serviço real de importação de asserções, em memória."""

    organization_id: OrganizationId
    frigorifico: ExternalCounterparty
    artifact_repo: RepositorioArtefatosEmMemoria
    assertion_repo: RepositorioAssertionsEmMemoria
    counterparty_repo: RepositorioContrapartesEmMemoria
    service: QualificationAssertionImportService

    @staticmethod
    def criar() -> RoteiroImportacaoQualificacao:
        organization_id = OrganizationId(uuid4())
        frigorifico = ExternalCounterparty(
            counterparty_id=TypedId.new("external_counterparty"),
            organization_id=organization_id,
            name="Frigorífico Demonstração LTDA",
            counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
        )
        artifact_repo = RepositorioArtefatosEmMemoria()
        assertion_repo = RepositorioAssertionsEmMemoria()
        counterparty_repo = RepositorioContrapartesEmMemoria()
        counterparty_repo.save(frigorifico)
        service = QualificationAssertionImportService(
            artifact_repository=artifact_repo,
            assertion_repository=assertion_repo,
            counterparty_repository=counterparty_repo,
        )
        return RoteiroImportacaoQualificacao(
            organization_id=organization_id,
            frigorifico=frigorifico,
            artifact_repo=artifact_repo,
            assertion_repo=assertion_repo,
            counterparty_repo=counterparty_repo,
            service=service,
        )

    def _contexto(self, actor_entity_type: str = "user") -> LivestockOperationContext:
        return LivestockOperationContext(
            organization_id=self.organization_id,
            actor_reference=UniversalReference(
                target_id=TypedId.new(actor_entity_type),
                organization_id=self.organization_id,
                contract_version=1,
            ),
            source_reference=UniversalReference(
                target_id=TypedId.new("system"),
                organization_id=self.organization_id,
                contract_version=1,
            ),
            correlation_id=TypedId.new("correlation"),
        )

    def parte_1_importacao_basica(self) -> None:
        _cabecalho("Parte 1: Importacao basica")
        _linha("Importar snapshot completo do MAPA com uma qualificacao.")

        resultado = self.service.import_assertions(
            context=self._contexto(),
            source="MAPA",
            source_version="2026-03-15T00:00Z",
            content_hash="sha256:v1-conteudo-do-snapshot",
            snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
            observed_at=datetime(2026, 3, 15, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=self.frigorifico.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.QUALIFIED,
                )
            ],
        )

        _linha(f"already_imported: {resultado.already_imported}")
        _linha(f"created_assertions: {resultado.created_assertions}")
        _linha(f"inferred_absence_assertions: {resultado.inferred_absence_assertions}")
        assert not resultado.already_imported
        assert resultado.created_assertions == 1

    def parte_2_idempotencia(self) -> None:
        _cabecalho("Parte 2: Idempotencia")
        _linha("Reimportar a MESMA source_version -- nao deve duplicar.")

        antes = len(self.assertion_repo.store)
        resultado = self.service.import_assertions(
            context=self._contexto(),
            source="MAPA",
            source_version="2026-03-15T00:00Z",  # mesma versão da parte 1
            content_hash="sha256:v1-conteudo-do-snapshot",
            snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
            observed_at=datetime(2026, 3, 15, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=self.frigorifico.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.QUALIFIED,
                )
            ],
        )
        depois = len(self.assertion_repo.store)

        _linha(f"already_imported: {resultado.already_imported}")
        _linha(f"assertions antes: {antes}, depois: {depois}")
        assert resultado.already_imported
        assert antes == depois

    def parte_3_ausencia_em_snapshot_completo(self) -> None:
        _cabecalho("Parte 3: Ausencia em snapshot completo produz UNKNOWN")
        _linha(
            "Nova versao do MAPA (27/07) nao lista mais o frigorifico para "
            "EXPORT_CN. Snapshot eh COMPLETE_SNAPSHOT nos dois lados.\n"
            "Esperado: uma Assertion derivada com status=UNKNOWN -- NUNCA "
            "NOT_QUALIFIED, porque o fato nao decide o que a ausencia significa."
        )

        outro_frigorifico = ExternalCounterparty(
            counterparty_id=TypedId.new("external_counterparty"),
            organization_id=self.organization_id,
            name="Outro Frigorífico (permanece na lista)",
            counterparty_type=CounterpartyType.SLAUGHTERHOUSE,
        )
        self.counterparty_repo.save(outro_frigorifico)

        resultado = self.service.import_assertions(
            context=self._contexto(),
            source="MAPA",
            source_version="2026-07-27T00:00Z",
            content_hash="sha256:v2-conteudo-do-snapshot",
            snapshot_semantics=SourceCoverage.COMPLETE_SNAPSHOT,
            observed_at=datetime(2026, 7, 27, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=outro_frigorifico.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.QUALIFIED,
                )
            ],
        )

        _linha(f"inferred_absence_assertions: {resultado.inferred_absence_assertions}")
        derivadas = [
            a
            for a in self.assertion_repo.store
            if a.establishment_id == self.frigorifico.counterparty_id
            and a.source_artifact_id == resultado.source_artifact_id
        ]
        for assertion in derivadas:
            _linha(
                f"  status={assertion.asserted_status.value} "
                f"effective_from={assertion.effective_from} "
                f"effective_until={assertion.effective_until} "
                f"confidence={assertion.confidence_tier.value}"
            )
        assert resultado.inferred_absence_assertions == 1
        assert derivadas[0].asserted_status == AssertionStatus.UNKNOWN
        assert derivadas[0].effective_from is None
        assert derivadas[0].effective_until is None

    def parte_4_snapshot_parcial_nao_infere(self) -> None:
        _cabecalho("Parte 4: Snapshot PARTIAL nao gera inferencia de ausencia")
        _linha(
            "Uma lista PARCIAL (ex.: so a regiao Sul) nao pode ser usada para "
            "concluir que quem nao aparece perdeu a qualificacao."
        )

        resultado = self.service.import_assertions(
            context=self._contexto(),
            source="MAPA",
            source_version="2026-07-28T00:00Z-regiao-sul",
            content_hash="sha256:v3-parcial",
            snapshot_semantics=SourceCoverage.PARTIAL,
            observed_at=datetime(2026, 7, 28, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=self.frigorifico.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.QUALIFIED,
                )
            ],
        )

        _linha(f"inferred_absence_assertions: {resultado.inferred_absence_assertions}")
        assert resultado.inferred_absence_assertions == 0

    def parte_5_conhecimento_historico_vs_retrospectivo(self) -> None:
        _cabecalho("Parte 5: Reproducao historica vs auditoria retrospectiva")
        _linha(
            "Uma nova fonte, hoje, revela que a habilitacao ja havia sido "
            "revogada explicitamente em uma data passada. A decisao historica "
            "nao eh reescrita; a auditoria retrospectiva enxerga a lacuna."
        )

        cutoff_da_decisao = datetime(2026, 7, 20, tzinfo=UTC)

        # Conhecimento posterior: revogacao explicita datada
        self.service.import_assertions(
            context=self._contexto(),
            source="FRIGORIFICO_XYZ",
            source_version="declaracao-2026-07-30",
            content_hash="sha256:declaracao",
            snapshot_semantics=SourceCoverage.DELTA,
            observed_at=datetime(2026, 7, 30, tzinfo=UTC),
            assertions=[
                QualificationAssertionInput(
                    establishment_id=self.frigorifico.counterparty_id,
                    qualification_type="EXPORT_CN",
                    asserted_status=AssertionStatus.NOT_QUALIFIED,
                    effective_from=datetime(2026, 7, 10, tzinfo=UTC),
                )
            ],
        )

        todas = self.assertion_repo.list_by_establishment(
            self.organization_id, self.frigorifico.counterparty_id
        )
        conhecidas_em_20_07 = [a for a in todas if a.known_as_of(cutoff_da_decisao)]
        cobrindo_15_07 = [a for a in todas if a.effective_at(datetime(2026, 7, 15, tzinfo=UTC))]

        _linha(f"Assertions conhecidas em 20/07 (reproducao historica): {len(conhecidas_em_20_07)}")
        for a in conhecidas_em_20_07:
            _linha(f"  status={a.asserted_status.value} observed_at={a.observed_at}")

        _linha(f"Assertions cobrindo 15/07 (auditoria retrospectiva): {len(cobrindo_15_07)}")
        for a in cobrindo_15_07:
            _linha(f"  status={a.asserted_status.value} effective_from={a.effective_from}")

        assert all(a.observed_at <= cutoff_da_decisao for a in conhecidas_em_20_07)
        assert any(a.asserted_status == AssertionStatus.NOT_QUALIFIED for a in cobrindo_15_07)

    def parte_6_confianca_computada(self) -> None:
        _cabecalho("Parte 6: Confianca computada pelo Titan, nunca declarada")
        _linha(
            "QualificationAssertionInput nao possui campo de confianca -- o "
            "cliente HTTP nao pode escolher o proprio grau de confianca."
        )

        assert not hasattr(QualificationAssertionInput, "confidence")
        assert not hasattr(QualificationAssertionInput, "confidence_tier")

        humano = compute_confidence(context=self._contexto(actor_entity_type="user"))
        automatizado = compute_confidence(context=self._contexto(actor_entity_type="system"))
        assinado = compute_confidence(
            context=self._contexto(actor_entity_type="user"),
            has_verified_signature=True,
        )

        _linha(f"Ator humano (upload manual):          {humano.value}")
        _linha(f"Ator system (integracao autenticada): {automatizado.value}")
        _linha(f"Com assinatura verificada:            {assinado.value}")

        assert humano == ConfidenceTier.DOCUMENTED
        assert automatizado == ConfidenceTier.VERIFIED_SOURCE
        assert assinado == ConfidenceTier.CRYPTOGRAPHICALLY_ATTESTED

    def executar(self) -> int:
        separador = "=" * 78
        _linha(separador)
        _linha("ROTEIRO: Importacao de Assercoes de Qualificacao (Marco 17.3a, ADR-0045)")
        _linha(separador)

        try:
            self.parte_1_importacao_basica()
            self.parte_2_idempotencia()
            self.parte_3_ausencia_em_snapshot_completo()
            self.parte_4_snapshot_parcial_nao_infere()
            self.parte_5_conhecimento_historico_vs_retrospectivo()
            self.parte_6_confianca_computada()

            _linha()
            _linha(separador)
            _linha("OK: ROTEIRO CONCLUIDO -- todas as afirmacoes do servico real se confirmaram.")
            _linha(separador)
            return 0
        except AssertionError as erro:
            _linha(f"\nFALHA: uma afirmacao do roteiro nao se confirmou: {erro}")
            traceback.print_exc()
            return 1
        except Exception as erro:  # noqa: BLE001 - roteiro de validacao manual
            _linha(f"\nERRO INESPERADO: {erro}")
            traceback.print_exc()
            return 2


def main(pausar: bool = False) -> int:
    roteiro = RoteiroImportacaoQualificacao.criar()
    resultado = roteiro.executar()

    if pausar:
        input("\nPressione ENTER para sair...")

    return resultado


if __name__ == "__main__":
    pausar_flag = "--pausar" in sys.argv
    sys.exit(main(pausar=pausar_flag))
