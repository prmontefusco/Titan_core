"""Composição com matriz de elegibilidade — BuyerPolicy Fase 3 Incremento 3 (ADR-0066).

Reutiliza os auxiliares de `test_policy_sharing_api` (montar Policy contratual,
compartilhá-la, criar Animal do fornecedor e produzir a Evaluation pela rota
pública) pelo mesmo motivo que `test_shared_policy_rate_limit` já reutiliza:
duplicar esse preparo faria as suítes divergirem no primeiro ajuste de contrato.

A Rule contratual do fixture usa `fact_type="test.fact"`, deliberadamente
fictício e nunca produzido por nenhum fact provider real — por isso a
Evaluation resultante nunca fica `CONDICOES_SATISFEITAS`/`CONDICOES_NAO_SATISFEITAS`,
sempre indeterminada. Isso é suficiente para provar o caminho `REQUER_REVISAO`
e toda a mecânica de isolamento/auditoria; os caminhos `ELEGIVEL`/`INELEGIVEL`
exigiriam uma Policy contratual com fato real resolvível e regra governada de
mercado adotada, fora do escopo deste corte de testes.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from packages.core_infrastructure.rate_limiter import (
    SHARED_POLICY_EVALUATIONS_PER_MINUTE,
    shared_policy_evaluation_rate_limiter,
)
from packages.livestock_application.authorization import OPERADOR_PECUARIO
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose
from tests.integration.test_policy_sharing_api import (
    _contract_policy,
    _evaluation_for_contract_policy,
    _headers,
    _share_policy,
)
from tests.livestock_api_support import (
    DATABASE_URL,
    PERMISSOES_OPERADOR,
    Ambiente,
    ClienteAutenticado,
    _cliente,
)

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada.")

_MERCADO = MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code


@pytest.fixture(autouse=True)
def _limitador_vazio() -> None:
    """Compose reutiliza a mesma cota do `/evaluate` (D3) -- cada teste comeca do zero."""
    shared_policy_evaluation_rate_limiter()._buckets.clear()


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def fornecedor(ambiente: Ambiente) -> ClienteAutenticado:
    principal = ambiente._principal_com_papel(
        subject=f"fornecedor-{uuid4().hex}",
        organizacao=ambiente.org_b,
        nome_papel=f"{OPERADOR_PECUARIO}_{uuid4().hex[:8]}",
        permissoes=tuple(sorted(PERMISSOES_OPERADOR)),
        agora=datetime.now(UTC),
    )
    return _cliente(ambiente, principal)


def _compor(
    operador: ClienteAutenticado,
    ambiente: Ambiente,
    *,
    policy_id: str,
    grant_id: str,
    evaluation_id: str,
    market: str = _MERCADO,
) -> Any:
    return operador.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/compose-with-matrix",
        json={"grant_id": grant_id, "evaluation_id": evaluation_id, "market": market},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )


def test_comprador_compoe_sem_regra_de_mercado_adotada_recebe_requer_revisao(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    resposta = _compor(
        operador, ambiente, policy_id=policy_id, grant_id=grant_id, evaluation_id=evaluation_id
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert set(corpo.keys()) == {"grant_id", "evaluation_id", "market", "composite_verdict"}
    assert corpo["grant_id"] == grant_id
    assert corpo["evaluation_id"] == evaluation_id
    assert corpo["market"] == _MERCADO
    assert corpo["composite_verdict"] == "REQUER_REVISAO"


def test_fornecedor_nao_pode_compor(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    resposta = fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/compose-with-matrix",
        json={"grant_id": grant_id, "evaluation_id": evaluation_id, "market": _MERCADO},
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )

    assert resposta.status_code == 403, resposta.text
    assert resposta.json()["reason_code"] == "GRANT_INVALIDO"


def test_compor_com_grant_inexistente_recebe_403(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    resposta = _compor(
        operador,
        ambiente,
        policy_id=policy_id,
        grant_id=str(uuid4()),
        evaluation_id=evaluation_id,
    )

    assert resposta.status_code == 403, resposta.text
    assert resposta.json()["reason_code"] == "GRANT_INVALIDO"


def test_compor_com_mercado_invalido_recebe_422(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    resposta = _compor(
        operador,
        ambiente,
        policy_id=policy_id,
        grant_id=grant_id,
        evaluation_id=evaluation_id,
        market="mercado-que-nao-existe",
    )

    assert resposta.status_code == 422, resposta.text
    assert resposta.json()["reason_code"] == "PARAMETRO_INVALIDO"


def test_compor_com_evaluation_inexistente_recebe_404(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)

    resposta = _compor(
        operador,
        ambiente,
        policy_id=policy_id,
        grant_id=grant_id,
        evaluation_id=str(uuid4()),
    )

    assert resposta.status_code == 404, resposta.text
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_compor_com_evaluation_de_outra_policy_recebe_404(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)

    outra_policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, outra_policy_id)
    evaluation_de_outra_policy = _evaluation_for_contract_policy(
        ambiente, fornecedor, outra_policy_id
    )

    resposta = _compor(
        operador,
        ambiente,
        policy_id=policy_id,
        grant_id=grant_id,
        evaluation_id=evaluation_de_outra_policy,
    )

    assert resposta.status_code == 404, resposta.text
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_compor_respeita_a_cota_do_grant(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    # A cota e por grant, compartilhada entre /evaluate e /compose-with-matrix
    # (D3): a Evaluation acima ja consumiu uma unidade.
    for _ in range(SHARED_POLICY_EVALUATIONS_PER_MINUTE - 1):
        resposta = _compor(
            operador,
            ambiente,
            policy_id=policy_id,
            grant_id=grant_id,
            evaluation_id=evaluation_id,
        )
        assert resposta.status_code == 201, resposta.text

    excedida = _compor(
        operador, ambiente, policy_id=policy_id, grant_id=grant_id, evaluation_id=evaluation_id
    )

    assert excedida.status_code == 429, excedida.text
    corpo = excedida.json()
    assert corpo["reason_code"] == "LIMITE_DE_AVALIACOES_EXCEDIDO"
    assert int(excedida.headers["Retry-After"]) > 0


def test_access_log_registra_compose_para_o_dono_da_policy(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)
    evaluation_id = _evaluation_for_contract_policy(ambiente, fornecedor, policy_id)

    resposta = _compor(
        operador, ambiente, policy_id=policy_id, grant_id=grant_id, evaluation_id=evaluation_id
    )
    assert resposta.status_code == 201, resposta.text

    trilha = operador.get(
        f"/v1/rule-governance/policies/{policy_id}/access-log",
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert trilha.status_code == 200, trilha.text
    itens = trilha.json()["items"]
    compose = next(item for item in itens if item["action"] == "COMPOSE")
    assert compose["http_status_code"] == 201
    assert compose["grant_id"] == grant_id
    assert compose["organization_id"] == str(ambiente.org_a.organization_id.value)
    assert compose["subject_id"] == _animal_id_from_evaluation(ambiente, evaluation_id)


def _animal_id_from_evaluation(ambiente: Ambiente, evaluation_id: str) -> str:
    from packages.core_infrastructure.persistence import set_local_organization_context
    from packages.core_infrastructure.persistence.evaluation import (
        TransactionalEvaluationRepository,
    )
    from packages.shared_kernel import TypedId

    set_local_organization_context(ambiente.connection, ambiente.org_b.organization_id)
    evaluation = TransactionalEvaluationRepository(ambiente.connection).get_by_id(
        TypedId.parse("evaluation", evaluation_id)
    )
    assert evaluation is not None
    return str(evaluation.subject_id.value)
