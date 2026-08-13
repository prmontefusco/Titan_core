from uuid import uuid4

from tests.livestock_api_support import _cliente


def test_cria_publica_e_consulta_policy(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    criada = cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={
            "code": f"politica-mercado-{uuid4().hex[:8]}",
            "name": "Politica de mercado interno",
            "description": "Rascunho fictício para validar o fluxo de governança.",
        },
    )
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert corpo["status"] == "draft"
    assert corpo["version"] == 1
    assert corpo["published_at"] is None

    publicada = cliente.post(
        f"/v1/rule-governance/policies/{corpo['policy_id']}/publish",
        headers=headers,
        json={},
    )
    assert publicada.status_code == 200, publicada.text
    publicada_corpo = publicada.json()
    assert publicada_corpo["status"] == "published"
    assert publicada_corpo["published_at"] is not None

    consultada = cliente.get(f"/v1/rule-governance/policies/{corpo['policy_id']}", headers=headers)
    assert consultada.status_code == 200
    assert consultada.json()["status"] == "published"


def test_lista_policies_da_organization(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    codigo = f"politica-lista-{uuid4().hex[:8]}"
    cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": codigo, "name": "Politica listada"},
    )

    listadas = cliente.get("/v1/rule-governance/policies", headers=headers)

    assert listadas.status_code == 200
    codigos = {item["code"] for item in listadas.json()["items"]}
    assert codigo in codigos


def test_publicar_policy_ja_publicada_e_recusado_com_conflito(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = cliente.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-dupla-{uuid4().hex[:8]}", "name": "Politica dupla publicacao"},
    ).json()["policy_id"]
    cliente.post(f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={})

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={}
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_publicar_policy_inexistente_retorna_404(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = cliente.post(
        f"/v1/rule-governance/policies/{uuid4()}/publish", headers=headers, json={}
    )

    assert resposta.status_code == 404
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_auditor_nao_cria_policy(ambiente) -> None:  # type: ignore[no-untyped-def]
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}

    resposta = _cliente(ambiente, ambiente.auditor).post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-negada-{uuid4().hex[:8]}", "name": "Nao deve criar"},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_auditor_nao_publica_policy_mas_le(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente_operador = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    policy_id = cliente_operador.post(
        "/v1/rule-governance/policies",
        headers=headers,
        json={"code": f"politica-leitura-{uuid4().hex[:8]}", "name": "Leitura do auditor"},
    ).json()["policy_id"]

    cliente_auditor = _cliente(ambiente, ambiente.auditor)
    negada = cliente_auditor.post(
        f"/v1/rule-governance/policies/{policy_id}/publish", headers=headers, json={}
    )
    assert negada.status_code == 403
    assert negada.json()["reason_code"] == "PERMISSAO_AUSENTE"

    permitida = cliente_auditor.get(f"/v1/rule-governance/policies/{policy_id}", headers=headers)
    assert permitida.status_code == 200


def test_criar_policy_com_codigo_repetido_e_recusado_com_conflito(ambiente) -> None:  # type: ignore[no-untyped-def]
    cliente = _cliente(ambiente, ambiente.operador)
    headers = {"X-Titan-Organization-Id": str(ambiente.org_a.organization_id.value)}
    codigo = f"politica-repetida-{uuid4().hex[:8]}"
    cliente.post(
        "/v1/rule-governance/policies", headers=headers, json={"code": codigo, "name": "Primeira"}
    )

    resposta = cliente.post(
        "/v1/rule-governance/policies", headers=headers, json={"code": codigo, "name": "Segunda"}
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"
