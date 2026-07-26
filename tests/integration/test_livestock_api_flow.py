"""O fluxo farmacológico inteiro, operado pela API (Passo 10.4b).

Este arquivo é a validação que o PLANO define para o Passo 10.4: operar o cenário
aprovado por HTTP, com **dois papéis** e **duas Organizations**, conferindo
negações, erros e isolamento.

O que ele percorre, do cadastro à prova:

    animal → medicamento → lote → tratamento → carência → decisão → dossiê

O ambiente reusa o do 10.4a, inclusive o role sem `BYPASSRLS`: sob o usuário
`titan`, que é superusuário, o isolamento não seria exercido de verdade.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from apps.api.livestock_dependencies import ORGANIZATION_HEADER
from tests.livestock_api_support import (
    DATABASE_URL,
    Ambiente,
    ClienteAutenticado,
    _cliente,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)


class Fluxo:
    """Executa o cenário pela API e guarda os identificadores devolvidos."""

    def __init__(self, ambiente: Ambiente, cliente: ClienteAutenticado) -> None:
        self.ambiente = ambiente
        self.cliente = cliente
        self.cabecalho = {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}

    def _post(self, rota: str, corpo: dict[str, Any] | None = None) -> Any:
        resposta = self.cliente.post(rota, json=corpo or {}, headers=self.cabecalho)
        assert resposta.status_code == 201, f"{rota}: {resposta.text}"
        return resposta.json()

    def executar(self, *, dias_atras: int = 10, carencia: int = 30) -> dict[str, str]:
        animal = self._post(
            "/v1/livestock/animals",
            {
                "birth_property_id": str(self.ambiente.property_id.value),
                "sex": "FEMALE",
                "breed": "Nelore",
            },
        )
        medicamento = self._post(
            "/v1/livestock/medications",
            {
                "trade_name": f"Ivomec-{datetime.now(UTC).timestamp()}",
                "active_ingredient": "Ivermectina",
                "manufacturer": "Boehringer",
                "withdrawal_period_days": carencia,
            },
        )
        assert medicamento["product_class"] == "PHARMACOLOGICAL"
        lote = self._post(
            "/v1/livestock/medication-batches",
            {
                "medication_id": medicamento["medication_id"],
                "batch_number": f"LOTE-{datetime.now(UTC).timestamp()}",
                "expiry_date": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
            },
        )
        campanha = self._post(
            "/v1/livestock/sanitary-campaigns",
            {
                "code": f"PNCEBT-BRUCELOSE-{datetime.now(UTC).timestamp()}",
                "name": "Campanha Brucelose",
                "starts_at": (datetime.now(UTC) - timedelta(days=dias_atras + 10)).isoformat(),
                "ends_at": (datetime.now(UTC) + timedelta(days=60)).isoformat(),
                "disease": "Brucelose",
                "authority": "MAPA",
            },
        )
        tratamento = self._post(
            "/v1/livestock/treatments",
            {
                "animal_id": animal["animal_id"],
                "medication_batch_id": lote["batch_id"],
                "applied_at": (datetime.now(UTC) - timedelta(days=dias_atras)).isoformat(),
                "dose": "1 mL / 50 kg",
                "sanitary_campaign_id": campanha["campaign_id"],
                "evidence_notes": ["foto no celular do João"],
            },
        )
        assert tratamento["sanitary_campaign_id"] == campanha["campaign_id"]
        elegibilidade = self._post(f"/v1/livestock/animals/{animal['animal_id']}/eligibility")
        return {
            "animal_id": animal["animal_id"],
            "campaign_code": campanha["code"],
            "campaign_id": campanha["campaign_id"],
            "batch_id": lote["batch_id"],
            "application_id": tratamento["application_id"],
            "decision_id": elegibilidade["decision_id"],
            "dossier_id": elegibilidade["dossier_id"],
            "result": elegibilidade["result"],
        }

    def registrar_veterinario(self, *, documentado: bool = True) -> dict[str, str]:
        veterinario = self._post(
            "/v1/livestock/veterinarians",
            {
                "name": f"Dra. Prescricao {datetime.now(UTC).timestamp()}",
                "cpf": f"{datetime.now(UTC).timestamp():.0f}".zfill(11)[-11:],
                "council_number": f"CRMV-{datetime.now(UTC).timestamp()}",
                "council_state": "MT",
            },
        )
        if not documentado:
            return cast(dict[str, str], veterinario)
        resposta = self.cliente.post(
            f"/v1/livestock/veterinarians/{veterinario['veterinarian_id']}/verification",
            json={"new_status": "DOCUMENTADO"},
            headers=self.cabecalho,
        )
        assert resposta.status_code == 201, resposta.text
        return cast(dict[str, str], resposta.json())


@pytest.fixture
def operador(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.operador)


@pytest.fixture
def auditor(ambiente: Ambiente) -> ClienteAutenticado:
    return _cliente(ambiente, ambiente.auditor)


def test_o_fluxo_farmacologico_inteiro_bloqueia_pela_api(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    """Tratado há 10 dias, carência de 30: o animal tem de ser reprovado."""
    resultado = Fluxo(ambiente, operador).executar(dias_atras=10, carencia=30)

    assert resultado["result"] == "rejeitada"
    assert resultado["dossier_id"]


def test_fora_da_carencia_a_decisao_aprova(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    resultado = Fluxo(ambiente, operador).executar(dias_atras=100, carencia=30)

    assert resultado["result"] == "aprovada"


def test_exigibilidade_sanitaria_minima_encontra_campanha_vinculada(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    resultado = Fluxo(ambiente, operador).executar(dias_atras=100, carencia=30)

    resposta = operador.get(
        "/v1/livestock/animals/"
        f"{resultado['animal_id']}/sanitary-requirements/{resultado['campaign_code']}",
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "ATENDIDA"
    assert corpo["campaign_id"] == resultado["campaign_id"]
    assert corpo["application_id"] == resultado["application_id"]
    assert corpo["gaps"] == []


def test_prescricao_veterinaria_e_emitida_e_detalhada_pela_api(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    fluxo = Fluxo(ambiente, operador)
    animal = fluxo._post(
        "/v1/livestock/animals",
        {"birth_property_id": str(ambiente.property_id.value), "sex": "FEMALE"},
    )
    medicamento = fluxo._post(
        "/v1/livestock/medications",
        {
            "trade_name": f"PrescMed-{datetime.now(UTC).timestamp()}",
            "active_ingredient": "Produto ficticio",
            "manufacturer": "Fabricante ficticio",
            "withdrawal_period_days": 7,
        },
    )
    lote = fluxo._post(
        "/v1/livestock/medication-batches",
        {
            "medication_id": medicamento["medication_id"],
            "batch_number": f"PRESC-{datetime.now(UTC).timestamp()}",
            "expiry_date": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
        },
    )
    veterinario = fluxo.registrar_veterinario()

    resposta = operador.post(
        "/v1/livestock/prescriptions",
        json={
            "veterinarian_id": veterinario["veterinarian_id"],
            "medication_id": medicamento["medication_id"],
            "property_id": str(ambiente.property_id.value),
            "dosage": "1 mL",
            "administration_route": "subcutanea",
            "target_type": "ANIMAL",
            "target_ids": [animal["animal_id"]],
            "reason": "Tratamento ficticio de validacao",
        },
        headers=fluxo.cabecalho,
    )

    assert resposta.status_code == 201, resposta.text
    prescricao = resposta.json()
    assert prescricao["veterinarian_id"] == veterinario["veterinarian_id"]
    assert prescricao["target_ids"] == [animal["animal_id"]]
    assert prescricao["administration_route"] == "SUBCUTANEA"

    detalhe = operador.get(
        f"/v1/livestock/prescriptions/{prescricao['prescription_id']}",
        headers=fluxo.cabecalho,
    )
    assert detalhe.status_code == 200, detalhe.text
    assert detalhe.json() == prescricao

    tratamento = operador.post(
        "/v1/livestock/treatments",
        json={
            "animal_id": animal["animal_id"],
            "medication_batch_id": lote["batch_id"],
            "applied_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "dose": "1 mL",
            "prescription_id": prescricao["prescription_id"],
        },
        headers=fluxo.cabecalho,
    )
    assert tratamento.status_code == 201, tratamento.text
    assert tratamento.json()["prescription_id"] == prescricao["prescription_id"]


def test_prescricao_recusa_veterinario_nao_documentado(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    fluxo = Fluxo(ambiente, operador)
    animal = fluxo._post(
        "/v1/livestock/animals",
        {"birth_property_id": str(ambiente.property_id.value), "sex": "MALE"},
    )
    medicamento = fluxo._post(
        "/v1/livestock/medications",
        {
            "trade_name": f"PrescNeg-{datetime.now(UTC).timestamp()}",
            "active_ingredient": "Produto ficticio",
            "manufacturer": "Fabricante ficticio",
            "withdrawal_period_days": 7,
        },
    )
    veterinario = fluxo.registrar_veterinario(documentado=False)

    resposta = operador.post(
        "/v1/livestock/prescriptions",
        json={
            "veterinarian_id": veterinario["veterinarian_id"],
            "medication_id": medicamento["medication_id"],
            "property_id": str(ambiente.property_id.value),
            "dosage": "1 mL",
            "administration_route": "subcutanea",
            "target_type": "ANIMAL",
            "target_ids": [animal["animal_id"]],
            "reason": "Tentativa ficticia",
        },
        headers=fluxo.cabecalho,
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_auditor_nao_emite_prescricao(ambiente: Ambiente, auditor: ClienteAutenticado) -> None:
    resposta = auditor.post(
        "/v1/livestock/prescriptions",
        json={},
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 403


def test_o_dossie_devolvido_verifica_se_pelo_proprio_hash(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """A prova entregue por HTTP é verificável sem o Titan."""
    from packages.core_domain.dossier import Dossier

    resultado = Fluxo(ambiente, operador).executar()

    resposta = auditor.get(
        f"/v1/livestock/dossiers/{resultado['dossier_id']}",
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 200
    dossier = Dossier.from_dict(resposta.json())
    assert dossier.verify()
    assert dossier.document["vertical"]["namespace"] == "livestock"


def test_a_linha_do_tempo_mostra_a_historia_pela_api(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    resultado = Fluxo(ambiente, operador).executar()

    resposta = auditor.get(
        f"/v1/livestock/animals/{resultado['animal_id']}/timeline",
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 200
    tipos = [entrada["entry_type"] for entrada in resposta.json()["entries"]]
    assert "livestock.animal_registered" in tipos
    assert "livestock.treatment_applied" in tipos
    assert "core.decision" in tipos


def test_a_correcao_cria_registro_novo_e_preserva_o_original(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """Não há rota de edição: corrigir acrescenta, e o corrigido continua visível."""
    resultado = Fluxo(ambiente, operador).executar()
    cabecalho = {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}

    correcao = operador.post(
        f"/v1/livestock/treatments/{resultado['application_id']}/corrections",
        json={
            "applied_at": (datetime.now(UTC) - timedelta(days=9)).isoformat(),
            "dose": "2 mL / 50 kg",
        },
        headers=cabecalho,
    )

    assert correcao.status_code == 201
    corpo = correcao.json()
    assert corpo["application_id"] != resultado["application_id"]
    assert corpo["corrects_application_id"] == resultado["application_id"]

    linha = auditor.get(
        f"/v1/livestock/animals/{resultado['animal_id']}/timeline", headers=cabecalho
    ).json()
    aplicacoes = [e for e in linha["entries"] if e["entry_type"] == "livestock.treatment_applied"]
    assert len(aplicacoes) == 2, "O registro corrigido não pode desaparecer."
    superseded = [e for e in aplicacoes if e["superseded_by"]]
    assert len(superseded) == 1


def test_o_auditor_nao_escreve(ambiente: Ambiente, auditor: ClienteAutenticado) -> None:
    """403 é 'sei quem você é, e você não pode' — distinto do 401."""
    resposta = auditor.post(
        "/v1/livestock/medications",
        json={
            "trade_name": "Qualquer",
            "active_ingredient": "Qualquer",
            "manufacturer": "Qualquer",
            "withdrawal_period_days": 10,
        },
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_o_operador_nao_le_dossie(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    """A separação vale nos dois sentidos: quem opera não recebe leitura de prova."""
    resultado = Fluxo(ambiente, operador).executar()

    resposta = operador.get(
        f"/v1/livestock/dossiers/{resultado['dossier_id']}",
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"


def test_outra_organizacao_nao_alcanca_o_dossie(
    ambiente: Ambiente, operador: ClienteAutenticado, auditor: ClienteAutenticado
) -> None:
    """Isolamento: pedir pela Org B não revela sequer que o dossiê existe."""
    resultado = Fluxo(ambiente, operador).executar()

    resposta = auditor.get(
        f"/v1/livestock/dossiers/{resultado['dossier_id']}",
        headers={ORGANIZATION_HEADER: str(ambiente.org_b.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "CONTEXTO_ORGANIZACIONAL_NEGADO"


def test_lote_de_medicamento_inexistente_devolve_404(
    ambiente: Ambiente, operador: ClienteAutenticado
) -> None:
    from uuid import uuid4

    resposta = operador.post(
        "/v1/livestock/medication-batches",
        json={
            "medication_id": str(uuid4()),
            "batch_number": "LOTE-X",
            "expiry_date": (datetime.now(UTC) + timedelta(days=100)).isoformat(),
        },
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 404
    assert resposta.json()["reason_code"] == "RECURSO_NAO_ENCONTRADO"


def test_tratamento_no_futuro_e_recusado(ambiente: Ambiente, operador: ClienteAutenticado) -> None:
    """O domínio recusa por regra, e o HTTP traduz para conflito, não para 500."""
    fluxo = Fluxo(ambiente, operador)
    animal = fluxo._post(
        "/v1/livestock/animals",
        {"birth_property_id": str(ambiente.property_id.value), "sex": "MALE"},
    )
    medicamento = fluxo._post(
        "/v1/livestock/medications",
        {
            "trade_name": f"Med-{datetime.now(UTC).timestamp()}",
            "active_ingredient": "X",
            "manufacturer": "Y",
            "withdrawal_period_days": 5,
        },
    )
    lote = fluxo._post(
        "/v1/livestock/medication-batches",
        {
            "medication_id": medicamento["medication_id"],
            "batch_number": f"L-{datetime.now(UTC).timestamp()}",
            "expiry_date": (datetime.now(UTC) + timedelta(days=200)).isoformat(),
        },
    )

    resposta = operador.post(
        "/v1/livestock/treatments",
        json={
            "animal_id": animal["animal_id"],
            "medication_batch_id": lote["batch_id"],
            "applied_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
        headers=fluxo.cabecalho,
    )

    assert resposta.status_code == 409
    assert resposta.json()["reason_code"] == "CONFLITO_DE_DOMINIO"
