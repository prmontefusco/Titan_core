"""Cenário demonstrativo reproduzível (Passo 10.6).

Executa, num comando, a sequência que o PLANO exige para o Marco 10:

    cadastro → tratamento → bloqueio → correção → reavaliação → dossiê

**Dados fictícios.** Nenhuma pessoa, propriedade ou animal aqui existe. Nomes de
medicamento e fabricante são reais porque a carência declarada só faz sentido
com o produto que a origina, mas nada é dado pessoal.

**O que a demonstração prova, e é o ponto do produto:** o Titan não apenas
bloqueia — ele **redecide sobre fatos corrigidos**, e guarda as duas decisões. A
narrativa é a de um operador que lança a data errada, o animal é barrado, o erro
é corrigido por novo registro, e a reavaliação libera. Nada foi apagado: as duas
avaliações, as duas decisões e as duas aplicações continuam legíveis.

Os artefatos ficam em disco ao final — o dossiê em JSON e em PDF — para poderem
ser inspecionados sem o Titan no ar.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Connection

from apps.seed.__main__ import Semeado, semear
from packages.core_application.dossier_service import DossierService
from packages.core_domain.decision import Decision, DecisionResult
from packages.core_domain.dossier import Dossier
from packages.core_domain.evaluation import Evaluation
from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.core_infrastructure.pdf import SoftwareDossierPdfAdapter
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.dossier import TransactionalDossierRepository
from packages.core_infrastructure.persistence.evaluation import (
    TransactionalEvaluationRepository,
)
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.livestock_application.animal_service import AnimalService
from packages.livestock_application.dossier_template import LivestockDossierTemplate
from packages.livestock_application.eligibility import PharmacologicalEligibilityService
from packages.livestock_application.eligibility_policy_provider import (
    EligibilityPolicyProvider,
)
from packages.livestock_application.event_recorder import (
    LivestockEventRecorder,
    LivestockOperationContext,
)
from packages.livestock_application.fact_provider import LivestockFactProvider
from packages.livestock_application.medication_service import (
    MedicationBatchService,
    MedicationService,
)
from packages.livestock_application.timeline_service import LivestockTimelineService
from packages.livestock_application.treatment_service import TreatmentApplicationService
from packages.livestock_application.withdrawal_service import WithdrawalCalculator
from packages.livestock_domain.animal import AnimalSex, IdentifierType
from packages.livestock_infrastructure.dossier_pdf_template import LivestockPdfTemplate
from packages.livestock_infrastructure.persistence.animal_repository import (
    TransactionalAnimalRepository,
)
from packages.livestock_infrastructure.persistence.lot_repository import (
    TransactionalLotMembershipRepository,
)
from packages.livestock_infrastructure.persistence.medication_repository import (
    TransactionalMedicationBatchRepository,
    TransactionalMedicationRepository,
    TransactionalPrescriptionRepository,
)
from packages.livestock_infrastructure.persistence.movement_repository import (
    TransactionalAnimalMovementRepository,
)
from packages.livestock_infrastructure.persistence.property_repository import (
    TransactionalRuralPropertyRepository,
)
from packages.livestock_infrastructure.persistence.treatment_repository import (
    TransactionalTreatmentApplicationRepository,
)
from packages.livestock_infrastructure.persistence.veterinarian_repository import (
    TransactionalVeterinarianRepository,
)
from packages.shared_kernel import SystemClock, TypedId, UniversalReference

CARENCIA_DIAS = 30
APLICACAO_ERRADA_DIAS_ATRAS = 10  # dentro da carência: bloqueia
APLICACAO_CORRETA_DIAS_ATRAS = 45  # fora da carência: libera

SISBOV_FICTICIO = "BR000000000001"


@dataclass(frozen=True, slots=True)
class Passo:
    numero: str
    titulo: str
    detalhe: str


class Demonstracao:
    """Monta os serviços uma vez e conduz a narrativa."""

    def __init__(self, connection: Connection, semeado: Semeado) -> None:
        self.connection = connection
        self.semeado = semeado
        self.passos: list[Passo] = []

        self.contexto = LivestockOperationContext(
            organization_id=semeado.org_a,
            actor_reference=UniversalReference(
                target_id=TypedId.new("actor"),
                organization_id=semeado.org_a,
                contract_version=1,
            ),
            source_reference=UniversalReference(
                target_id=TypedId.new("demonstracao"),
                organization_id=semeado.org_a,
                contract_version=1,
            ),
            correlation_id=TypedId.new("correlation"),
        )

        self.animal_repository = TransactionalAnimalRepository(connection=connection)
        self.batch_repository = TransactionalMedicationBatchRepository(connection=connection)
        self.medication_repository = TransactionalMedicationRepository(connection=connection)
        self.application_repository = TransactionalTreatmentApplicationRepository(
            connection=connection
        )
        self.recorder = LivestockEventRecorder(
            event_log=DomainEventRepository(connection=connection), clock=SystemClock()
        )

    def _anotar(self, numero: str, titulo: str, detalhe: str) -> None:
        self.passos.append(Passo(numero, titulo, detalhe))

    def executar(self) -> dict[str, Any]:
        animal = AnimalService(
            repository=self.animal_repository, recorder=self.recorder
        ).register_animal(
            context=self.contexto,
            birth_property_id=self.semeado.property_id,
            sex=AnimalSex.FEMALE,
            breed="Nelore",
            initial_identifier_type=IdentifierType.OFFICIAL_SISBOV,
            initial_identifier_value=SISBOV_FICTICIO,
        )
        self._anotar("1", "Cadastro", f"Novilha Nelore registrada com SISBOV {SISBOV_FICTICIO}.")

        medicamento = MedicationService(
            medication_repository=self.medication_repository,
            prescription_repository=TransactionalPrescriptionRepository(connection=self.connection),
            veterinarian_repository=TransactionalVeterinarianRepository(connection=self.connection),
            property_repository=TransactionalRuralPropertyRepository(connection=self.connection),
            recorder=self.recorder,
        ).register_medication(
            context=self.contexto,
            trade_name=f"Antiparasitario Demonstracao {datetime.now(UTC).timestamp():.0f}",
            active_ingredient="Ivermectina",
            manufacturer="Fabricante Ficticio S.A.",
            withdrawal_period_days=CARENCIA_DIAS,
        )
        lote = MedicationBatchService(
            batch_repository=self.batch_repository,
            medication_repository=self.medication_repository,
            recorder=self.recorder,
        ).register_batch(
            context=self.contexto,
            medication_id=medicamento.medication_id,
            batch_number=f"LOTE-DEMO-{datetime.now(UTC).timestamp():.0f}",
            expiry_date=datetime.now(UTC) + timedelta(days=365),
        )
        self._anotar(
            "2",
            "Insumo",
            f"Medicamento com carência de {CARENCIA_DIAS} dias, e um lote rastreável.",
        )

        tratamento = TreatmentApplicationService(
            application_repository=self.application_repository,
            animal_repository=self.animal_repository,
            batch_repository=self.batch_repository,
            prescription_repository=TransactionalPrescriptionRepository(connection=self.connection),
            recorder=self.recorder,
            evidence_lookup=TransactionalEvidenceRepository(connection=self.connection),
        )
        aplicacao = tratamento.register_application(
            context=self.contexto,
            animal_id=animal.animal_id,
            medication_batch_id=lote.batch_id,
            applied_at=datetime.now(UTC) - timedelta(days=APLICACAO_ERRADA_DIAS_ATRAS),
            dose="1 mL / 50 kg",
            evidence_notes=("anotacao do operador em campo",),
        )
        self._anotar(
            "3",
            "Tratamento",
            f"Aplicação lançada como há {APLICACAO_ERRADA_DIAS_ATRAS} dias — data que o "
            "operador informou errado.",
        )

        avaliacao_1, decisao_1 = self._avaliar(animal.animal_id)
        self._anotar(
            "4",
            "Bloqueio",
            f"Elegibilidade avaliada: {decisao_1.result.value.upper()}. "
            f"{decisao_1.reasons[0].message if decisao_1.reasons else ''}",
        )

        correcao = tratamento.correct_application(
            context=self.contexto,
            original_application_id=aplicacao.application_id,
            applied_at=datetime.now(UTC) - timedelta(days=APLICACAO_CORRETA_DIAS_ATRAS),
            dose="1 mL / 50 kg",
            evidence_notes=("nota fiscal confirma a data real da compra",),
        )
        self._anotar(
            "5",
            "Correção",
            f"A data real era há {APLICACAO_CORRETA_DIAS_ATRAS} dias. Novo registro criado; "
            "o anterior permanece, marcado como corrigido.",
        )

        avaliacao_2, decisao_2 = self._avaliar(animal.animal_id)
        self._anotar(
            "6",
            "Reavaliação",
            f"Nova elegibilidade sobre os fatos corrigidos: {decisao_2.result.value.upper()}.",
        )

        dossie = self._dossie(decisao_2, avaliacao_2)
        self._anotar(
            "7",
            "Dossiê",
            f"Prova emitida e verificável: hash {dossie.dossier_hash[:16]}…",
        )

        linha = LivestockTimelineService(
            event_reader=DomainEventRepository(connection=self.connection),
            movement_repository=TransactionalAnimalMovementRepository(connection=self.connection),
            application_repository=self.application_repository,
            membership_repository=TransactionalLotMembershipRepository(connection=self.connection),
            batch_repository=self.batch_repository,
            evaluation_repository=TransactionalEvaluationRepository(connection=self.connection),
            decision_repository=TransactionalDecisionRepository(connection=self.connection),
        ).animal_timeline(self.semeado.org_a, animal.animal_id)

        return {
            "animal_id": animal.animal_id,
            "aplicacao_original": aplicacao.application_id,
            "aplicacao_corrigida": correcao.application_id,
            "decisao_1": decisao_1,
            "decisao_2": decisao_2,
            "dossie": dossie,
            "linha_do_tempo": linha,
        }

    def _politica_vigente(self) -> tuple[Policy, Rule]:
        return EligibilityPolicyProvider(
            policy_repository=TransactionalPolicyRepository(connection=self.connection),
            rule_repository=TransactionalRuleRepository(connection=self.connection),
        ).current(self.semeado.org_a)

    def _avaliar(self, animal_id: TypedId) -> tuple[Evaluation, Decision]:
        policy, rule = self._politica_vigente()
        return PharmacologicalEligibilityService(
            fact_provider=LivestockFactProvider(
                property_repository=TransactionalRuralPropertyRepository(
                    connection=self.connection
                ),
                animal_repository=self.animal_repository,
                withdrawal_calculator=WithdrawalCalculator(
                    application_repository=self.application_repository,
                    batch_repository=self.batch_repository,
                    medication_repository=self.medication_repository,
                ),
            ),
            policy=policy,
            rule=rule,
            evaluation_repository=TransactionalEvaluationRepository(connection=self.connection),
            decision_repository=TransactionalDecisionRepository(connection=self.connection),
        ).evaluate_animal(self.semeado.org_a, animal_id, datetime.now(UTC))

    def _dossie(self, decisao: Decision, avaliacao: Evaluation) -> Dossier:
        policy, rule = self._politica_vigente()
        repositorio = TransactionalDossierRepository(connection=self.connection)
        dossie = LivestockDossierTemplate(
            timeline_service=LivestockTimelineService(
                event_reader=DomainEventRepository(connection=self.connection),
                movement_repository=TransactionalAnimalMovementRepository(
                    connection=self.connection
                ),
                application_repository=self.application_repository,
                membership_repository=TransactionalLotMembershipRepository(
                    connection=self.connection
                ),
                batch_repository=self.batch_repository,
                evaluation_repository=TransactionalEvaluationRepository(connection=self.connection),
                decision_repository=TransactionalDecisionRepository(connection=self.connection),
            ),
            application_repository=self.application_repository,
            evidence_lookup=TransactionalEvidenceRepository(connection=self.connection),
            dossier_service=DossierService(repository=repositorio),
        ).build(decision=decisao, evaluation=avaliacao, policy=policy, rules=[rule])
        repositorio.save(dossie)
        return dossie


def _gravar_artefatos(dossie: Dossier, destino: Path) -> tuple[Path, Path]:
    destino.mkdir(parents=True, exist_ok=True)
    caminho_json = destino / f"dossie-{dossie.dossier_id.value}.json"
    caminho_json.write_text(
        json.dumps(dossie.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    representacao = SoftwareDossierPdfAdapter(
        vertical_templates=[LivestockPdfTemplate()]
    ).generate_pdf(dossie)
    caminho_pdf = destino / f"dossie-{dossie.dossier_id.value}.pdf"
    caminho_pdf.write_bytes(representacao.pdf_bytes)
    return caminho_json, caminho_pdf


def _relatorio(demo: Demonstracao, resultado: dict[str, Any], artefatos: tuple[Path, Path]) -> str:
    linhas = ["", "=" * 62, "CENÁRIO DEMONSTRATIVO — fluxo farmacológico completo", "=" * 62, ""]
    for passo in demo.passos:
        linhas.append(f"  {passo.numero}. {passo.titulo}")
        linhas.append(f"     {passo.detalhe}")
        linhas.append("")

    decisao_1: Decision = resultado["decisao_1"]
    decisao_2: Decision = resultado["decisao_2"]
    dossie: Dossier = resultado["dossie"]
    linha = resultado["linha_do_tempo"]
    tratamentos = [e for e in linha if e.entry_type == "livestock.treatment_applied"]

    linhas += [
        "-" * 62,
        "O QUE FICOU PROVADO",
        "-" * 62,
        "",
        f"  Decisão 1 (fatos originais) ....... {decisao_1.result.value.upper()}",
        f"  Decisão 2 (fatos corrigidos) ...... {decisao_2.result.value.upper()}",
        "",
        "  As duas decisões existem e são distintas: o Titan redecidiu sobre",
        "  fatos corrigidos sem apagar a decisão anterior.",
        "",
        f"  Aplicações na linha do tempo ...... {len(tratamentos)}",
        f"  Aplicações marcadas como corrigidas {len([e for e in tratamentos if e.superseded_by])}",
        "",
        "  O registro errado continua legível, marcado. Corrigir acrescentou;",
        "  não sobrescreveu.",
        "",
        f"  Entradas na linha do tempo ........ {len(linha)}",
        f"  Dossiê verifica-se sozinho ........ {dossie.verify()}",
        "",
        "-" * 62,
        "ARTEFATOS GRAVADOS",
        "-" * 62,
        "",
        f"  JSON: {artefatos[0]}",
        f"  PDF : {artefatos[1]}",
        "",
        "  O JSON é a prova. Recalcule o SHA-256 dos seus bytes canônicos e",
        "  compare com o campo dossier_hash — sem o Titan no ar.",
        "",
        "=" * 62,
    ]
    return "\n".join(linhas)


def main() -> None:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    if os.environ.get("TITAN_SEED_CONFIRM") != "1":
        raise SystemExit(
            "Esta demonstração grava dados fictícios e cria usuários com senha "
            "conhecida.\nDefina TITAN_SEED_CONFIRM=1 para confirmar que o ambiente "
            "é local e descartável."
        )

    issuer = os.environ.get("TITAN_OIDC_ISSUER", "http://localhost:8080/realms/titan").rstrip("/")
    destino = Path(os.environ.get("TITAN_DEMO_OUTPUT", "artefatos-demonstracao"))

    engine = create_database_engine(DatabaseSettings.from_environment())
    try:
        with engine.connect() as connection, connection.begin():
            # A demonstração roda numa transação só: ou o cenário inteiro existe,
            # ou nada dele existe. Cenário pela metade confunde quem o inspeciona.
            semeado = semear(
                connection,
                issuer=issuer,
                subs={"operador": "demo-operador", "auditor": "demo-auditor"},
            )
            demo = Demonstracao(connection, semeado)
            resultado = demo.executar()
            artefatos = _gravar_artefatos(resultado["dossie"], destino)
            print(_relatorio(demo, resultado, artefatos))

            if resultado["decisao_1"].result is not DecisionResult.REJEITADA:
                raise SystemExit("O cenário deveria bloquear na primeira avaliação.")
            if resultado["decisao_2"].result is not DecisionResult.APROVADA:
                raise SystemExit("A reavaliação deveria aprovar após a correção.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
