"""Integração HTTP do pedido de tipo de entidade (EntityTypeRequest).

Prova a travessia completa que a arquitetura promete: alguém sem Membership
nenhum consegue pedir, ninguém ganha acesso sozinho, e só depois de aprovado o
pedido vira Membership/Role reais — usáveis na mesma requisição seguinte.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.core_domain.authentication import AuthenticatedPrincipal, PrincipalType
from packages.livestock_application.authorization import ADMINISTRACAO
from tests.livestock_api_support import DATABASE_URL, ISSUER, Ambiente, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


def _sem_vinculo() -> AuthenticatedPrincipal:
    """Um Access Token válido de alguém que o Titan nunca viu antes."""
    return AuthenticatedPrincipal(
        issuer=ISSUER,
        subject=f"pretendente-{uuid4().hex}",
        principal_type=PrincipalType.USER,
        authenticated_at=datetime.now(UTC),
        client_id="titan-swagger",
        technical_scopes=frozenset({"openid"}),
    )


def _admin(ambiente: Ambiente) -> AuthenticatedPrincipal:
    """Master admin da org_a: só a permissão de decidir EntityTypeRequest."""
    return ambiente._principal_com_papel(
        subject=f"admin-{uuid4().hex}",
        organizacao=ambiente.org_a,
        nome_papel=f"ADMIN_MESTRE_{uuid4().hex[:8]}",
        permissoes=tuple(sorted(ADMINISTRACAO)),
        agora=datetime.now(UTC),
    )


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}


def test_submeter_pedido_sem_vinculo_previo(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())

    resposta = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={
            "organization_id": str(ambiente.org_a.organization_id.value),
            "requested_kind": "PRODUTOR",
        },
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "PENDENTE"
    assert corpo["requested_kind"] == "PRODUTOR"
    assert corpo["decided_at"] is None


def test_segundo_pedido_pendente_da_mesma_pessoa_e_recusado(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())
    payload = {
        "organization_id": str(ambiente.org_a.organization_id.value),
        "requested_kind": "PRODUTOR",
    }

    primeira = pretendente.post("/v1/livestock/entity-type-requests", json=payload)
    assert primeira.status_code == 201, primeira.text

    segunda = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={**payload, "requested_kind": "AUDITOR"},
    )
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["reason_code"] == "PEDIDO_PENDENTE_JA_EXISTE"


def test_listar_pendentes_exige_permissao_de_decisao(ambiente: Ambiente) -> None:
    auditor = _cliente(ambiente, ambiente.auditor)

    resposta = auditor.get("/v1/livestock/entity-type-requests", headers=_cabecalho(ambiente))

    assert resposta.status_code == 403, resposta.text
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_fluxo_completo_aprovado_concede_acesso_real(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())
    admin = _cliente(ambiente, _admin(ambiente))

    submissao = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={
            "organization_id": str(ambiente.org_a.organization_id.value),
            "requested_kind": "AUDITOR",
        },
    )
    assert submissao.status_code == 201, submissao.text
    request_id = submissao.json()["request_id"]

    pendentes = admin.get("/v1/livestock/entity-type-requests", headers=_cabecalho(ambiente))
    assert pendentes.status_code == 200, pendentes.text
    assert any(item["request_id"] == request_id for item in pendentes.json())

    aprovacao = admin.post(
        f"/v1/livestock/entity-type-requests/{request_id}/approve",
        headers=_cabecalho(ambiente),
    )
    assert aprovacao.status_code == 200, aprovacao.text
    assert aprovacao.json()["status"] == "APROVADA"

    # A prova real: o mesmo principal, sem mais nada, agora consegue usar o
    # próprio contexto organizacional que acabou de ganhar -- não é só um status
    # mudando de nome, é Membership e Role de verdade na mesma Organization. O
    # papel concedido a um AUDITOR não inclui ENTITY_TYPE_REQUEST_LER (fica de
    # fora de LEITURA de propósito), então a prova é 403 e não mais 401/404: o
    # principal existe e tem vínculo, só não tem esta permissão específica.
    proxima_chamada = pretendente.get(
        "/v1/livestock/entity-type-requests", headers=_cabecalho(ambiente)
    )
    assert proxima_chamada.status_code == 403, proxima_chamada.text
    assert proxima_chamada.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_negar_pedido_nao_concede_acesso(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())
    admin = _cliente(ambiente, _admin(ambiente))

    submissao = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={
            "organization_id": str(ambiente.org_a.organization_id.value),
            "requested_kind": "CONSUMIDOR",
        },
    )
    request_id = submissao.json()["request_id"]

    negacao = admin.post(
        f"/v1/livestock/entity-type-requests/{request_id}/deny",
        json={"reason": "Sem evidência de vínculo com a Organization."},
        headers=_cabecalho(ambiente),
    )
    assert negacao.status_code == 200, negacao.text
    assert negacao.json()["status"] == "NEGADA"

    ainda_sem_vinculo = pretendente.get(
        "/v1/livestock/entity-type-requests", headers=_cabecalho(ambiente)
    )
    assert ainda_sem_vinculo.status_code == 403, ainda_sem_vinculo.text


def test_aprovar_pedido_ja_decidido_falha(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())
    admin = _cliente(ambiente, _admin(ambiente))

    submissao = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={
            "organization_id": str(ambiente.org_a.organization_id.value),
            "requested_kind": "CERTIFICADOR",
        },
    )
    request_id = submissao.json()["request_id"]

    primeira = admin.post(
        f"/v1/livestock/entity-type-requests/{request_id}/approve",
        headers=_cabecalho(ambiente),
    )
    assert primeira.status_code == 200, primeira.text

    segunda = admin.post(
        f"/v1/livestock/entity-type-requests/{request_id}/approve",
        headers=_cabecalho(ambiente),
    )
    assert segunda.status_code == 409, segunda.text
    assert segunda.json()["reason_code"] == "PEDIDO_JA_DECIDIDO"


def test_meu_status_antes_de_pedir_nao_tem_vinculo_nem_pedido(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())

    resposta = pretendente.get(
        "/v1/livestock/entity-type-requests/mine", headers=_cabecalho(ambiente)
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo == {"has_membership": False, "requests": []}


def test_meu_status_acompanha_pendente_depois_aprovado(ambiente: Ambiente) -> None:
    pretendente = _cliente(ambiente, _sem_vinculo())
    admin = _cliente(ambiente, _admin(ambiente))

    submissao = pretendente.post(
        "/v1/livestock/entity-type-requests",
        json={
            "organization_id": str(ambiente.org_a.organization_id.value),
            "requested_kind": "VETERINARIO",
        },
    )
    request_id = submissao.json()["request_id"]

    pendente = pretendente.get(
        "/v1/livestock/entity-type-requests/mine", headers=_cabecalho(ambiente)
    )
    assert pendente.status_code == 200, pendente.text
    corpo_pendente = pendente.json()
    assert corpo_pendente["has_membership"] is False
    assert len(corpo_pendente["requests"]) == 1
    assert corpo_pendente["requests"][0]["request_id"] == request_id
    assert corpo_pendente["requests"][0]["status"] == "PENDENTE"

    admin.post(
        f"/v1/livestock/entity-type-requests/{request_id}/approve", headers=_cabecalho(ambiente)
    )

    depois = pretendente.get(
        "/v1/livestock/entity-type-requests/mine", headers=_cabecalho(ambiente)
    )
    assert depois.status_code == 200, depois.text
    corpo_depois = depois.json()
    assert corpo_depois["has_membership"] is True
    assert corpo_depois["requests"][0]["status"] == "APROVADA"
