"""Saída do rebanho pela API (Passo 13.1).

O que estes testes provam é que a saída não é um campo: ela sai do rebanho ativo
por derivação, o banco recusa a segunda saída mesmo que o serviço falhasse em
conferir, e o passado continua alcançável — pelo detalhe, pela listagem histórica
e pelo lançamento atrasado de um fato anterior.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import DATABASE_URL, Ambiente, ClienteAutenticado, _cliente

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def _cabecalho(ambiente: Ambiente) -> dict[str, str]:
    return {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}


def _criar_animal(ambiente: Ambiente, operador: ClienteAutenticado) -> str:
    resposta = operador.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
        headers=_cabecalho(ambiente),
    )
    assert resposta.status_code == 201, resposta.text
    return str(resposta.json()["animal_id"])


def _registrar_saida(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    animal_id: str,
    quando: datetime,
    tipo: str = "ABATE",
) -> Any:
    return operador.post(
        f"/v1/livestock/animals/{animal_id}/exit",
        json={
            "exit_type": tipo,
            "occurred_at": quando.isoformat(),
            "reason": "Abate programado",
            "destination": "Frigorífico Central",
        },
        headers=_cabecalho(ambiente),
    )


def test_o_animal_que_saiu_deixa_o_rebanho_ativo(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    quando = datetime.now(UTC) - timedelta(days=1)

    criacao = _registrar_saida(ambiente, operador, animal_id, quando)
    assert criacao.status_code == 201, criacao.text

    listagem = operador.get("/v1/livestock/animals?limit=200", headers=_cabecalho(ambiente))
    assert animal_id not in [item["animal_id"] for item in listagem.json()["items"]]

    # Sair do rebanho não é desaparecer: o registro continua alcançável, e o
    # detalhe diz por quê.
    detalhe = operador.get(f"/v1/livestock/animals/{animal_id}", headers=_cabecalho(ambiente))
    assert detalhe.status_code == 200
    saida = detalhe.json()["saida"]
    assert saida["exit_type"] == "ABATE"
    assert saida["destination"] == "Frigorífico Central"


def test_saida_por_venda_referencia_contraparte_externa(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": "Fazenda Destino",
            "counterparty_type": "FARM",
            "identifiers": ["CAR:MT-0000000-0000"],
        },
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text

    saida = operador.post(
        f"/v1/livestock/animals/{animal_id}/exit",
        json={
            "exit_type": "VENDA",
            "occurred_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "reason": "Venda para recria",
            "destination_counterparty_id": contraparte.json()["counterparty_id"],
        },
        headers=_cabecalho(ambiente),
    )

    assert saida.status_code == 201, saida.text
    assert saida.json()["destination_counterparty_id"] == contraparte.json()["counterparty_id"]


def test_artefato_recebido_declara_lacuna_de_cobertura(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": "Fazenda Origem",
            "counterparty_type": "FARM",
            "identifiers": ["CAR:MT-1111111-1111"],
        },
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text
    transferencia = datetime.now(UTC) - timedelta(days=1)
    conhecido_ate = transferencia - timedelta(hours=10)

    registro = operador.post(
        f"/v1/livestock/animals/{animal_id}/received-transfer-artifacts",
        json={
            "source_counterparty_id": contraparte.json()["counterparty_id"],
            "bundle_digest": "a" * 64,
            "bundle_issued_at": conhecido_ate.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_from": (transferencia - timedelta(days=300)).isoformat(),
            "coverage_known_until": conhecido_ate.isoformat(),
            "issuer_name": "Fazenda Origem",
        },
        headers=_cabecalho(ambiente),
    )

    assert registro.status_code == 201, registro.text
    assert registro.json()["coverage"]["gaps"][0]["code"] == "COVERAGE_BEFORE_TRANSFER"


def test_aquisicao_documental_orquestra_artefato_e_fatos_importados(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": "Fazenda Origem",
            "counterparty_type": "FARM",
            "identifiers": ["CAR:MT-3333333-3333"],
        },
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text
    transferencia = datetime.now(UTC) - timedelta(days=1)

    resposta = operador.post(
        f"/v1/livestock/animals/{animal_id}/documentary-acquisitions",
        json={
            "source_counterparty_id": contraparte.json()["counterparty_id"],
            "bundle_digest": "d" * 64,
            "bundle_issued_at": transferencia.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_from": (transferencia - timedelta(days=180)).isoformat(),
            "coverage_known_until": transferencia.isoformat(),
            "issuer_name": "Fazenda Origem",
            "imported_facts": [
                {
                    "fact_type": "livestock.treatment_applied",
                    "occurred_at": (transferencia - timedelta(days=30)).isoformat(),
                    "asserted_by": "Fazenda Origem",
                    "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
                    "payload": {"withdrawal_period_days": 45},
                }
            ],
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["artifact"]["issuer_name"] == "Fazenda Origem"
    assert resposta.json()["imported_facts"][0]["origin"] == "IMPORTED_ASSERTION"
    assert (
        resposta.json()["imported_facts"][0]["source_artifact_id"]
        == resposta.json()["artifact"]["artifact_id"]
    )

    fatos = operador.get(
        f"/v1/livestock/animals/{animal_id}/imported-facts",
        headers=_cabecalho(ambiente),
    )
    assert fatos.status_code == 200, fatos.text
    assert fatos.json()["items"][0]["asserted_by"] == "Fazenda Origem"


def test_fato_importado_preserva_origem_externa(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={"name": "Fazenda Origem", "counterparty_type": "FARM"},
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text
    transferencia = datetime.now(UTC) - timedelta(days=1)
    artefato = operador.post(
        f"/v1/livestock/animals/{animal_id}/received-transfer-artifacts",
        json={
            "source_counterparty_id": contraparte.json()["counterparty_id"],
            "bundle_digest": "c" * 64,
            "bundle_issued_at": transferencia.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_until": transferencia.isoformat(),
        },
        headers=_cabecalho(ambiente),
    )
    assert artefato.status_code == 201, artefato.text

    fato = operador.post(
        f"/v1/livestock/animals/{animal_id}/imported-facts",
        json={
            "source_artifact_id": artefato.json()["artifact_id"],
            "fact_type": "livestock.treatment_applied",
            "occurred_at": (transferencia - timedelta(days=30)).isoformat(),
            "asserted_by": "Fazenda Origem",
            "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
            "payload": {"withdrawal_period_days": 45},
        },
        headers=_cabecalho(ambiente),
    )

    assert fato.status_code == 201, fato.text
    assert fato.json()["origin"] == "IMPORTED_ASSERTION"
    assert fato.json()["asserted_by"] == "Fazenda Origem"


def test_fato_importado_alimenta_elegibilidade(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={"name": "Fazenda Origem", "counterparty_type": "FARM"},
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text
    transferencia = datetime.now(UTC) - timedelta(days=1)
    artefato = operador.post(
        f"/v1/livestock/animals/{animal_id}/received-transfer-artifacts",
        json={
            "source_counterparty_id": contraparte.json()["counterparty_id"],
            "bundle_digest": "e" * 64,
            "bundle_issued_at": transferencia.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_until": transferencia.isoformat(),
        },
        headers=_cabecalho(ambiente),
    )
    assert artefato.status_code == 201, artefato.text
    fato = operador.post(
        f"/v1/livestock/animals/{animal_id}/imported-facts",
        json={
            "source_artifact_id": artefato.json()["artifact_id"],
            "fact_type": "livestock.treatment_applied",
            "occurred_at": (transferencia - timedelta(days=30)).isoformat(),
            "asserted_by": "Fazenda Origem",
            "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
            "payload": {"withdrawal_period_days": 45},
        },
        headers=_cabecalho(ambiente),
    )
    assert fato.status_code == 201, fato.text

    elegibilidade = operador.post(
        f"/v1/livestock/animals/{animal_id}/eligibility",
        headers=_cabecalho(ambiente),
    )

    assert elegibilidade.status_code == 201, elegibilidade.text
    assert elegibilidade.json()["result"] == "rejeitada"


def test_dossie_de_elegibilidade_declara_cobertura_recebida(
    ambiente: Ambiente,
    operador: ClienteAutenticado,
    auditor: ClienteAutenticado,
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": "Fazenda Origem",
            "counterparty_type": "FARM",
            "identifiers": ["CAR:MT-2222222-2222"],
        },
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text
    transferencia = datetime.now(UTC) - timedelta(days=1)
    conhecido_ate = transferencia - timedelta(hours=8)

    artefato = operador.post(
        f"/v1/livestock/animals/{animal_id}/received-transfer-artifacts",
        json={
            "source_counterparty_id": contraparte.json()["counterparty_id"],
            "bundle_digest": "f" * 64,
            "bundle_issued_at": conhecido_ate.isoformat(),
            "transfer_effective_at": transferencia.isoformat(),
            "coverage_known_from": (transferencia - timedelta(days=180)).isoformat(),
            "coverage_known_until": conhecido_ate.isoformat(),
            "issuer_name": "Fazenda Origem",
        },
        headers=_cabecalho(ambiente),
    )
    assert artefato.status_code == 201, artefato.text

    elegibilidade = operador.post(
        f"/v1/livestock/animals/{animal_id}/eligibility",
        headers=_cabecalho(ambiente),
    )
    assert elegibilidade.status_code == 201, elegibilidade.text

    dossie = auditor.get(
        f"/v1/livestock/dossiers/{elegibilidade.json()['dossier_id']}",
        headers=_cabecalho(ambiente),
    )
    assert dossie.status_code == 200, dossie.text

    coverage = dossie.json()["document"]["vertical"]["content"]["coverage"]
    assert coverage["status"] == "PARTIAL_DECLARED"
    assert coverage["basis"] == "received_transfer_artifact"
    assert coverage["has_declared_gaps"] is True
    assert coverage["gaps"][0]["code"] == "COVERAGE_BEFORE_TRANSFER"


def test_qualificacao_de_estabelecimento_e_registrada_por_mercado(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={
            "name": "Frigorifico Habilitado",
            "counterparty_type": "SLAUGHTERHOUSE",
            "identifiers": ["SIF:1234"],
        },
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text

    resposta = operador.post(
        f"/v1/livestock/external-counterparties/{contraparte.json()['counterparty_id']}/establishment-qualifications",
        json={
            "market_purpose": "exportacao-china",
            "status": "HABILITADO",
            "source_name": "lista-sif-ficticia",
            "source_version": "2026-07",
            "assessed_at": datetime.now(UTC).isoformat(),
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["counterparty_id"] == contraparte.json()["counterparty_id"]
    assert resposta.json()["market_purpose"] == "exportacao-china"
    assert resposta.json()["status"] == "HABILITADO"


def test_qualificacao_de_estabelecimento_recusa_contraparte_que_nao_e_frigorifico(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={"name": "Fazenda Origem", "counterparty_type": "FARM"},
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text

    resposta = operador.post(
        f"/v1/livestock/external-counterparties/{contraparte.json()['counterparty_id']}/establishment-qualifications",
        json={
            "market_purpose": "exportacao-china",
            "status": "HABILITADO",
            "source_name": "lista-sif-ficticia",
            "assessed_at": datetime.now(UTC).isoformat(),
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_auditor_nao_registra_qualificacao_de_estabelecimento(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={"name": "Frigorifico", "counterparty_type": "SLAUGHTERHOUSE"},
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text

    resposta = auditor.post(
        f"/v1/livestock/external-counterparties/{contraparte.json()['counterparty_id']}/establishment-qualifications",
        json={
            "market_purpose": "exportacao-china",
            "status": "HABILITADO",
            "source_name": "lista-sif-ficticia",
            "assessed_at": datetime.now(UTC).isoformat(),
        },
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_importacao_de_qualificacao_recusa_mesma_versao_com_hash_diferente(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    contraparte = operador.post(
        "/v1/livestock/external-counterparties",
        json={"name": "Frigorifico MAPA", "counterparty_type": "SLAUGHTERHOUSE"},
        headers=_cabecalho(ambiente),
    )
    assert contraparte.status_code == 201, contraparte.text

    corpo = {
        "source": "MAPA",
        "source_version": "2026-07-29T12:00:00Z",
        "content_hash": "sha256:aaa",
        "snapshot_semantics": "COMPLETE_SNAPSHOT",
        "observed_at": "2026-07-29T12:00:00Z",
        "assertions": [
            {
                "establishment_id": contraparte.json()["counterparty_id"],
                "qualification_type": "EXPORT_CN",
                "asserted_status": "QUALIFIED",
            }
        ],
    }
    primeira = operador.post(
        "/v1/livestock/establishments/qualification-assertions/import",
        json=corpo,
        headers=_cabecalho(ambiente),
    )
    assert primeira.status_code == 201, primeira.text

    resposta = operador.post(
        "/v1/livestock/establishments/qualification-assertions/import",
        json={**corpo, "content_hash": "sha256:bbb"},
        headers=_cabecalho(ambiente),
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["reason_code"] == "SOURCE_VERSION_CONTENT_HASH_CONFLICT"


def test_o_levantamento_historico_traz_quem_saiu_com_a_saida_preenchida(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    animal_id = _criar_animal(ambiente, operador)
    _registrar_saida(ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=1))

    listagem = operador.get(
        "/v1/livestock/animals?limit=200&incluir_saidos=true", headers=_cabecalho(ambiente)
    )

    encontrados = {item["animal_id"]: item for item in listagem.json()["items"]}
    assert animal_id in encontrados
    assert encontrados[animal_id]["saida"]["exit_type"] == "ABATE"


def test_a_segunda_saida_e_recusada(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    animal_id = _criar_animal(ambiente, operador)
    _registrar_saida(ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=2))

    repetida = _registrar_saida(
        ambiente, operador, animal_id, datetime.now(UTC) - timedelta(days=1), tipo="VENDA"
    )

    assert repetida.status_code == 409, repetida.text
    assert repetida.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_auditor_nao_registra_saida(ambiente: Ambiente, auditor: ClienteAutenticado) -> None:
    """Declarar a morte de um animal é escrita, e o auditor não escreve."""
    operador = _cliente(ambiente, ambiente.operador)
    animal_id = _criar_animal(ambiente, operador)

    negada = _registrar_saida(ambiente, auditor, animal_id, datetime.now(UTC) - timedelta(days=1))

    assert negada.status_code == 403, negada.text


def test_animal_inexistente_responde_404(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    resposta = _registrar_saida(
        ambiente,
        operador,
        "00000000-0000-4000-8000-000000000000",
        datetime.now(UTC) - timedelta(days=1),
    )

    assert resposta.status_code == 404, resposta.text
