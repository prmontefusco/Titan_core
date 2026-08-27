"""Rate-limit e trilha de acesso da BuyerPolicy compartilhada (Fase 3 Incremento 2).

Os testes reutilizam os auxiliares de `test_policy_sharing_api`: montar uma
Policy contratual publicada e compartilha-la e exatamente o preparo da Fase 2, e
duplicar esse preparo faria as duas suites divergirem no primeiro ajuste de
contrato.
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
from tests.integration.test_policy_sharing_api import (
    _animal_do_fornecedor,
    _contract_policy,
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


@pytest.fixture(autouse=True)
def _limitador_vazio() -> None:
    """Cada teste comeca com a cota inteira.

    O limitador vive na memoria do processo, e nao na transacao revertida ao fim
    do teste: sem esta limpeza, um teste que exaure a cota deixaria o proximo
    comecando pela metade.
    """
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


def _avaliar(
    fornecedor: ClienteAutenticado,
    ambiente: Ambiente,
    policy_id: str,
    subject_id: str,
) -> Any:
    return fornecedor.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        json={
            "subject_type": "ANIMAL",
            "subject_id": subject_id,
            "purpose": "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR",
            "reference_time": datetime.now(UTC).isoformat(),
        },
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )


def _esgotar_cota(
    fornecedor: ClienteAutenticado, ambiente: Ambiente, policy_id: str, animal_id: str
) -> None:
    """Consome a cota do minuto reavaliando o mesmo sujeito.

    Repetir a avaliacao do mesmo animal e exatamente o que a cota existe para
    conter: e assim que se reconstroi, por tentativa e erro, o criterio
    contratual que a Policy nao expoe.
    """
    for _ in range(SHARED_POLICY_EVALUATIONS_PER_MINUTE):
        resposta = _avaliar(fornecedor, ambiente, policy_id, animal_id)
        assert resposta.status_code == 201, resposta.text


def test_avaliacao_dentro_do_limite_permanece_201(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)

    _esgotar_cota(fornecedor, ambiente, policy_id, animal_id)


def test_avaliacao_acima_do_limite_recebe_429_com_retry_after(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)
    _esgotar_cota(fornecedor, ambiente, policy_id, animal_id)

    excedida = _avaliar(fornecedor, ambiente, policy_id, animal_id)

    assert excedida.status_code == 429, excedida.text
    corpo = excedida.json()
    assert corpo["reason_code"] == "LIMITE_DE_AVALIACOES_EXCEDIDO"
    assert corpo["limit_per_minute"] == SHARED_POLICY_EVALUATIONS_PER_MINUTE
    assert corpo["retry_after_seconds"] > 0
    assert int(excedida.headers["Retry-After"]) > 0


def test_cota_e_por_grant_e_nao_por_organization(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    exaurida = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, exaurida)
    vizinha = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, vizinha)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)

    _esgotar_cota(fornecedor, ambiente, exaurida, animal_id)
    assert _avaliar(fornecedor, ambiente, exaurida, animal_id).status_code == 429

    # Mesma Organization, mesmo sujeito, outro contrato: a cota exaurida nao
    # contamina o vizinho.
    assert _avaliar(fornecedor, ambiente, vizinha, animal_id).status_code == 201


def test_access_log_registra_leitura_e_avaliacao_da_beneficiaria(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    grant_id = _share_policy(operador, ambiente, policy_id)

    leitura = fornecedor.get(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert leitura.status_code == 200, leitura.text
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)
    assert _avaliar(fornecedor, ambiente, policy_id, animal_id).status_code == 201

    trilha = operador.get(
        f"/v1/rule-governance/policies/{policy_id}/access-log",
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert trilha.status_code == 200, trilha.text
    itens = trilha.json()["items"]
    assert [item["action"] for item in itens] == ["EVALUATE", "READ"]
    assert {item["http_status_code"] for item in itens} == {201, 200}
    assert {item["grant_id"] for item in itens} == {grant_id}
    assert {item["organization_id"] for item in itens} == {
        str(ambiente.org_b.organization_id.value)
    }
    avaliacao = next(item for item in itens if item["action"] == "EVALUATE")
    assert avaliacao["subject_type"] == "ANIMAL"
    assert avaliacao["subject_id"] == animal_id


def test_access_log_preserva_a_recusa_por_limite(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)
    _esgotar_cota(fornecedor, ambiente, policy_id, animal_id)
    assert _avaliar(fornecedor, ambiente, policy_id, animal_id).status_code == 429

    recusas = operador.get(
        f"/v1/rule-governance/policies/{policy_id}/access-log",
        params={"http_status_code": 429},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert recusas.status_code == 200, recusas.text
    itens = recusas.json()["items"]
    assert len(itens) == 1
    assert itens[0]["subject_id"] == animal_id
    assert itens[0]["action"] == "EVALUATE"

    concedidas = operador.get(
        f"/v1/rule-governance/policies/{policy_id}/access-log",
        params={"http_status_code": 201},
        headers=_headers(str(ambiente.org_a.organization_id.value)),
    )
    assert len(concedidas.json()["items"]) == SHARED_POLICY_EVALUATIONS_PER_MINUTE


def test_access_log_e_invisivel_para_quem_nao_e_dono_da_policy(
    ambiente: Ambiente, operador: ClienteAutenticado, fornecedor: ClienteAutenticado
) -> None:
    policy_id = _contract_policy(operador, ambiente)
    _share_policy(operador, ambiente, policy_id)
    animal_id = _animal_do_fornecedor(ambiente, fornecedor)
    assert _avaliar(fornecedor, ambiente, policy_id, animal_id).status_code == 201

    # A beneficiaria enxerga a Policy compartilhada, mas nao a trilha de acesso:
    # a resposta e a mesma de Policy inexistente, para nao virar oraculo.
    resposta = fornecedor.get(
        f"/v1/rule-governance/policies/{policy_id}/access-log",
        headers=_headers(str(ambiente.org_b.organization_id.value)),
    )
    assert resposta.status_code == 404
