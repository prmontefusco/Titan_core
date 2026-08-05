"""Roteiro executavel da revisao humana oficial de decisao (LIV-C06).

python -m uv run --locked python -m apps.validacao.revisao_humana_decisao
python -m uv run --locked python -m apps.validacao.revisao_humana_decisao --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import create_engine

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import (
    AMARELO,
    CINZA,
    FIM,
    NEGRITO,
    Cliente,
    Requisicao,
    Resposta,
    Roteiro,
)
from packages.core_application.decision_governance_service import DecisionGovernanceService
from packages.core_domain.evaluation import (
    Evaluation,
    EvaluationOutcome,
    RuleResult,
    RuleResultStatus,
    compute_context_hash,
    compute_evaluation_hash,
    compute_rule_inputs_hash,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.rule import SeverityLevel
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.decision_governance import (
    TransactionalDecisionGovernanceRepository,
)
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.livestock_application.eligibility import ELIGIBILITY_PURPOSE, ELIGIBILITY_RULE_CODE
from packages.livestock_application.eligibility_policy_provider import EligibilityPolicyProvider
from packages.shared_kernel import OrganizationId, TypedId


def _exigir_permissoes(cliente: Cliente) -> None:
    inexistente = "00000000-0000-4000-8000-000000000000"
    sondas = [
        cliente.get(f"/v1/livestock/decision-proposals/{inexistente}"),
        cliente.post(
            f"/v1/livestock/decision-proposals/{inexistente}/reviews",
            {"conclusion": "DEVOLVE", "reasoning": "sonda"},
        ),
    ]
    if all(sonda.status != 403 for sonda in sondas):
        return
    raise SystemExit(
        f"{AMARELO}O papel desta Organization nao tem as permissoes do LIV-C06.{FIM}\n"
        "Semeie novamente e reinicie a API com a operadora nova para carregar a "
        "permissao de revisao humana."
    )


def _criar_proposta_formal(
    *,
    database_url: str,
    organization_id: str,
    animal_id: str,
) -> dict[str, str]:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            organizacao = OrganizationId(UUID(organization_id))
            set_local_organization_context(connection, organizacao)

            policy, rule = EligibilityPolicyProvider(
                policy_repository=TransactionalPolicyRepository(connection=connection),
                rule_repository=TransactionalRuleRepository(connection=connection),
            ).current(organizacao)

            instante = datetime.now(UTC)
            alvo = TypedId(entity_type="animal", value=UUID(animal_id))
            snapshot = FactSnapshot.create(
                organization_id=organizacao,
                target_id=alvo,
                as_of=instante,
                facts=(
                    Fact.create(
                        fact_type="livestock.withdrawal",
                        payload={"in_withdrawal": False},
                        observed_at=instante,
                        accepted_at=instante,
                        known_at=instante,
                    ),
                    Fact.create(
                        fact_type="sanitary.attestation",
                        payload={"result": "approved"},
                        observed_at=instante,
                        accepted_at=instante,
                        known_at=instante,
                    ),
                    Fact.create(
                        fact_type="sanitary.attestation",
                        payload={"result": "rejected"},
                        observed_at=instante,
                        accepted_at=instante,
                        known_at=instante,
                    ),
                ),
            )
            rule_result = RuleResult.create(
                rule_id=rule.rule_id,
                rule_version=rule.version,
                organization_id=organizacao,
                subject_id=alvo,
                status=RuleResultStatus.INDETERMINADA,
                severity=SeverityLevel(rule.severity.value),
                reason="Evidencia sanitaria conflitante exige revisao humana oficial.",
                corrective_action="Registrar a conclusao formal de revisao.",
                evaluated_at=instante,
                snapshot_hash=snapshot.snapshot_hash,
                inputs_hash=compute_rule_inputs_hash(
                    rule.rule_id,
                    rule.version,
                    alvo,
                    snapshot.snapshot_hash,
                    (),
                ),
                rule_code=ELIGIBILITY_RULE_CODE,
            )
            context_hash = compute_context_hash(
                policy_id=policy.policy_id,
                policy_version=policy.version,
                purpose=ELIGIBILITY_PURPOSE,
                engine_version=1,
                rule_versions=((rule.code, rule.version),),
            )
            outcome = EvaluationOutcome.EVIDENCIA_CONFLITANTE
            evaluation = Evaluation(
                evaluation_id=TypedId.new("evaluation"),
                organization_id=organizacao,
                subject_id=alvo,
                purpose=ELIGIBILITY_PURPOSE,
                policy_id=policy.policy_id,
                policy_version=policy.version,
                fact_snapshot=snapshot,
                rule_results=(rule_result,),
                outcome=outcome,
                evaluated_at=instante,
                engine_version=1,
                evaluation_hash=compute_evaluation_hash(
                    context_hash=context_hash,
                    subject_id=alvo,
                    snapshot_hash=snapshot.snapshot_hash,
                    rule_results=(rule_result,),
                    outcome=outcome,
                ),
                context_hash=context_hash,
                rule_versions=((rule.code, rule.version),),
            )
            TransactionalEvaluationRepository(connection).save(evaluation)
            proposal = DecisionGovernanceService(
                repository=TransactionalDecisionGovernanceRepository(connection)
            ).create_proposal(evaluation)
            return {
                "evaluation_id": str(evaluation.evaluation_id.value),
                "proposal_id": str(proposal.proposal_id.value),
            }
    finally:
        engine.dispose()


def _montar_roteiro(
    *,
    operador: Cliente,
    auditor: Cliente,
    property_id: str,
    database_url: str,
    organization_id: str,
) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("LIV-C06 - Revisao humana oficial de decisao", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador encontra uma propriedade da Organization",
        lambda: operador.get("/v1/livestock/properties?limit=1"),
        200,
        conferir=lambda r: None if r["items"] else "nenhuma propriedade disponivel",
        guardar=lambda r: ids.update(property_id=str(r["items"][0]["property_id"])),
        porque="O roteiro descobre o contexto sozinho; nenhum identificador e copiado a mao.",
    )
    roteiro.passo(
        "2",
        "Operador cria o animal que recebera a proposta formal",
        lambda: operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": property_id, "sex": "FEMALE", "breed": "Nelore"},
        ),
        201,
        guardar=lambda r: ids.update(animal_id=str(r["animal_id"])),
        porque="A revisao humana continua ancorada em um sujeito real da vertical.",
    )
    roteiro.passo(
        "3",
        "Preparar Evaluation e Proposal formais para o fluxo oficial",
        lambda: Resposta(
            201,
            _criar_proposta_formal(
                database_url=database_url,
                organization_id=organization_id,
                animal_id=ids["animal_id"],
            ),
        ),
        201,
        conferir=lambda r: (
            None
            if r["proposal_id"] and r["evaluation_id"]
            else "setup nao gerou proposal/evaluation"
        ),
        guardar=lambda r: ids.update(
            proposal_id=str(r["proposal_id"]),
            evaluation_id=str(r["evaluation_id"]),
        ),
        porque=(
            "O caso minimo prepara material conflitante sem depender de copiar ids "
            "nem de fixtures manuais."
        ),
    )
    roteiro.passo(
        "4",
        "Operador consulta a proposta corrente pela API oficial",
        lambda: operador.get(f"/v1/livestock/decision-proposals/{ids['proposal_id']}"),
        200,
        conferir=lambda r: (
            None
            if r["proposal_id"] == ids["proposal_id"]
            and r["current_proposal"] is True
            and r["review_count"] == 0
            else "a proposta nao voltou como corrente e sem reviews"
        ),
        porque=(
            "A etapa prova que a proposal formal saiu do estado interno e virou "
            "recurso consultavel."
        ),
    )
    roteiro.passo(
        "5",
        "Operador registra a aprovacao humana e dispara a emissao oficial",
        lambda: operador.post(
            f"/v1/livestock/decision-proposals/{ids['proposal_id']}/reviews",
            {
                "conclusion": "APROVA",
                "reasoning": "Conflito sanitario revisado e aceito para emissao humana oficial.",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["workflow_status"] == "DECISION_EMITTED" and r["decision_id"] and r["dossier_id"]
            else "a review nao emitiu Decision e Dossier"
        ),
        guardar=lambda r: ids.update(
            review_id=str(r["review_id"]),
            decision_id=str(r["decision_id"]),
            dossier_id=str(r["dossier_id"]),
        ),
        porque=(
            "Permission executa a operacao tecnica; a autoridade resolvida pelo "
            "servidor fecha o fluxo oficial."
        ),
    )
    roteiro.passo(
        "6",
        "Auditor consulta o Dossier e verifica a trilha de governanca",
        lambda: auditor.get(f"/v1/livestock/dossiers/{ids['dossier_id']}"),
        200,
        conferir=lambda r: (
            None
            if r["document"]["governance"]["proposal"]["proposal_id"] == ids["proposal_id"]
            and r["document"]["governance"]["reviews"][0]["review_id"] == ids["review_id"]
            and r["document"]["decision"]["emission_method"] == "HUMAN"
            else "o dossie nao preservou a trilha de governanca esperada"
        ),
        porque="O Dossier e a prova canônica; o PDF continua sendo apenas apresentacao derivada.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do LIV-C06.")
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para preparar a proposal formal.")
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []
    operador = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="operador",
        diario=diario,
    )
    auditor = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_auditor",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="auditor",
        diario=diario,
    )

    _exigir_permissoes(operador)
    propriedade = operador.get("/v1/livestock/properties?limit=1")
    if propriedade.status != 200 or not propriedade["items"]:
        raise SystemExit("Nenhuma propriedade encontrada para iniciar o roteiro.")
    property_id = str(propriedade["items"][0]["property_id"])

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(
        f"{CINZA}  Rode a semeadura novamente se vier 403 para revisao humana "
        f"ou leitura do Dossier.{FIM}"
    )

    codigo = _montar_roteiro(
        operador=operador,
        auditor=auditor,
        property_id=property_id,
        database_url=database_url,
        organization_id=organizacao,
    ).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
