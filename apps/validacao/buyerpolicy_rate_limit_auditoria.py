"""Roteiro executavel para BuyerPolicy Fase 3 Incremento 2.

Rate-limit por grant e trilha de acesso a Policy compartilhada.

python -m uv run --locked python -m apps.validacao.buyerpolicy_rate_limit_auditoria
python -m uv run --locked python -m apps.validacao.buyerpolicy_rate_limit_auditoria --pausar
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import (
    CLIENTE_DE_VALIDACAO,
    _ambiente,
    _descobrir_organizacao,
)
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
from packages.core_infrastructure.rate_limiter import SHARED_POLICY_EVALUATIONS_PER_MINUTE

_FINALIDADE = "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR"


def _avaliar(cliente: Cliente, policy_id: str, sujeito: str) -> Resposta:
    return cliente.post(
        f"/v1/rule-governance/policies/shared-policies/{policy_id}/evaluate",
        {
            "subject_type": "ANIMAL",
            "subject_id": sujeito,
            "purpose": _FINALIDADE,
            "reference_time": datetime.now(UTC).isoformat(),
        },
    )


def _consumir_cota_restante(cliente: Cliente, policy_id: str) -> Resposta:
    """Leva o grant ate a ultima avaliacao ainda permitida.

    A primeira avaliacao ja foi feita no passo anterior; este passo completa a
    cota do minuto e devolve a ultima resposta, que ainda deve ser 201.
    """
    resposta = Resposta(0, None)
    for tentativa in range(1, SHARED_POLICY_EVALUATIONS_PER_MINUTE):
        resposta = _avaliar(cliente, policy_id, f"validacao-sujeito-{tentativa}")
        if resposta.status != 201:
            return resposta
    return resposta


def _acoes(corpo: Any) -> list[str]:
    return [item["action"] for item in corpo["items"]]


def _montar_roteiro(cliente: Cliente, organizacao: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("BuyerPolicy Fase 3 - rate-limit e trilha de acesso", diario=cliente.diario)

    roteiro.passo(
        "0",
        "Sondar ambiente autenticado",
        lambda: cliente.get("/technical/authentication"),
        200,
        porque="Falha aqui indica API, Keycloak, token ou OrganizationContext fora do lugar.",
    )
    roteiro.passo(
        "1",
        "Criar Policy contratual de apoio",
        lambda: cliente.post(
            "/v1/rule-governance/policies",
            {
                "code": f"rate-limit-{uuid4().hex[:8]}",
                "name": "Policy contratual de validacao de rate-limit",
                "description": "Registro ficticio criado pelo roteiro executavel.",
            },
        ),
        201,
        guardar=lambda r: ids.update(policy_id=str(r["policy_id"])),
        porque="A cota e a trilha existem sempre dentro de uma Policy compartilhada.",
    )
    roteiro.passo(
        "2",
        "Criar identidade de Rule contratual",
        lambda: cliente.post(
            "/v1/rule-governance/rule-identities",
            {
                "code": f"rate-limit-rule-{uuid4().hex[:8]}",
                "purpose": "Validar cota e trilha de acesso compartilhado.",
                "scope": "Policy compartilhada ficticia.",
                "source_type": "contrato",
                "vertical": "livestock",
                "description": "Identidade ficticia para o roteiro executavel.",
            },
        ),
        201,
        guardar=lambda r: ids.update(rule_identity_id=str(r["rule_identity_id"])),
        porque="A origem CONTRACT fica na identidade governada da regra.",
    )
    roteiro.passo(
        "3",
        "Publicar Rule contratual minima",
        lambda: cliente.post(
            f"/v1/rule-governance/rule-identities/{ids['rule_identity_id']}/versions",
            {
                "policy_id": ids["policy_id"],
                "name": "Valor de teste deve estar presente",
                "description": "Rule ficticia para permitir a autoavaliacao compartilhada.",
                "severity": "blocking",
                "normative_source": "Contrato ficticio de validacao",
                "required_evidence_types": [],
                "conditions": [
                    {
                        "fact_type": "test.fact",
                        "payload_key": "value",
                        "operator": "equals",
                        "expected_value": "test",
                    }
                ],
                "justification": "Permite exercitar a rota compartilhada da Fase 2.",
                "corrective_action": "Corrigir valor de teste.",
            },
        ),
        201,
        porque="O compartilhamento da Fase 2 exige Policy homogeneamente CONTRACT.",
    )
    roteiro.passo(
        "4",
        "Publicar Policy contratual",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/{ids['policy_id']}/publish",
            {"published_at": datetime.now(UTC).isoformat()},
        ),
        200,
        porque="Somente Policy publicada pode ser compartilhada.",
    )
    roteiro.passo(
        "5",
        "Compartilhar a Policy e obter o grant",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/{ids['policy_id']}/shares",
            {
                "beneficiary_organization_id": organizacao,
                "access_purpose": _FINALIDADE,
                "valid_until": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                "field_scope_profile": "CONTRATO_MINIMO",
            },
        ),
        201,
        guardar=lambda r: ids.update(grant_id=str(r["grant_id"])),
        porque="A cota do minuto e por grant, e nao por Organization nem por IP.",
    )
    roteiro.passo(
        "6",
        "Ler a Policy compartilhada",
        lambda: cliente.get(
            f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}",
        ),
        200,
        porque="Toda leitura sob grant deixa uma linha READ na trilha de acesso.",
    )
    roteiro.passo(
        "7",
        "Primeira autoavaliacao compartilhada",
        lambda: _avaliar(cliente, ids["policy_id"], "validacao-sujeito-0"),
        201,
        porque="A avaliacao dentro da cota segue respondendo normalmente.",
    )
    roteiro.passo(
        "8",
        f"Consumir a cota do minuto ({SHARED_POLICY_EVALUATIONS_PER_MINUTE} por grant)",
        lambda: _consumir_cota_restante(cliente, ids["policy_id"]),
        201,
        porque="A ultima avaliacao permitida ainda e concedida; a proxima nao deve ser.",
    )
    roteiro.passo(
        "9",
        "Exceder a cota e receber 429",
        lambda: _avaliar(cliente, ids["policy_id"], "validacao-sujeito-excedente"),
        429,
        conferir=lambda r: (
            None
            if r["reason_code"] == "LIMITE_DE_AVALIACOES_EXCEDIDO" and r["retry_after_seconds"] > 0
            else "recusa sem codigo estavel ou sem tempo de espera"
        ),
        porque="Repetir avaliacao e o caminho barato para inferir o criterio contratual.",
    )
    roteiro.passo(
        "10",
        "Listar a trilha de acesso pela Organization dona",
        lambda: cliente.get(f"/v1/rule-governance/policies/{ids['policy_id']}/access-log"),
        200,
        conferir=lambda r: (
            None
            if _acoes(r.corpo).count("READ") == 1
            and _acoes(r.corpo).count("EVALUATE") == SHARED_POLICY_EVALUATIONS_PER_MINUTE + 1
            else "trilha nao registrou a leitura e as avaliacoes esperadas"
        ),
        porque="O grant diz que o acesso era permitido; a trilha diz que ele aconteceu.",
    )
    roteiro.passo(
        "11",
        "Isolar a recusa por limite na trilha",
        lambda: cliente.get(
            f"/v1/rule-governance/policies/{ids['policy_id']}/access-log?http_status_code=429"
        ),
        200,
        conferir=lambda r: (
            None
            if len(r.corpo["items"]) == 1
            and r.corpo["items"][0]["subject_id"] == "validacao-sujeito-excedente"
            else "a recusa por limite nao ficou preservada na trilha"
        ),
        porque="Sem a recusa registrada, a varredura de dataset nao deixa rastro.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(
        description="Roteiro de rate-limit e auditoria da BuyerPolicy compartilhada."
    )
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = _ambiente("TITAN_DATABASE_URL", "")
    if not database_url and not opcoes.organizacao:
        raise SystemExit(
            "Defina TITAN_DATABASE_URL (para descobrir a Organization) ou passe --organizacao."
        )
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []
    cliente = Cliente(
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

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"  Cota por grant: {SHARED_POLICY_EVALUATIONS_PER_MINUTE} avaliacoes por minuto")
    print(f"{CINZA}  Rode seed/bootstrap novamente se vier 403 por permissao ausente.{FIM}")
    print(
        f"{CINZA}  A cota e por grant, e cada execucao cria um grant novo: repetir o "
        f"roteiro no mesmo minuto nao herda a cota da execucao anterior.{FIM}"
    )

    codigo = _montar_roteiro(cliente, organizacao).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
