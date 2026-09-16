"""Roteiro executavel para BuyerPolicy Fase 3 Incremento 3 (ADR-0066).

Composicao explicita (Fluxo B) da avaliacao contratual compartilhada com a
matriz de elegibilidade regulatoria -- somente o comprador (owner do grant)
compoe; o fornecedor nunca ve o efeito da matriz.

python -m uv run --locked python -m apps.validacao.buyerpolicy_composicao_matriz
python -m uv run --locked python -m apps.validacao.buyerpolicy_composicao_matriz --pausar
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose

_FINALIDADE = "AUTOAVALIACAO_CONTRATUAL_FORNECEDOR"
_MERCADO = MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code


def _montar_roteiro(cliente: Cliente, organizacao: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro(
        "BuyerPolicy Fase 3 Incremento 3 - composicao com a matriz", diario=cliente.diario
    )

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
                "code": f"compose-matriz-{uuid4().hex[:8]}",
                "name": "Policy contratual de validacao de composicao",
                "description": "Registro ficticio criado pelo roteiro executavel.",
            },
        ),
        201,
        guardar=lambda r: ids.update(policy_id=str(r["policy_id"])),
        porque="A composicao sempre parte de uma Policy contratual ja compartilhada.",
    )
    roteiro.passo(
        "2",
        "Criar identidade de Rule contratual",
        lambda: cliente.post(
            "/v1/rule-governance/rule-identities",
            {
                "code": f"compose-matriz-rule-{uuid4().hex[:8]}",
                "purpose": "Validar composicao com a matriz de elegibilidade.",
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
        porque="Compose-with-matrix exige um grant ATIVO entre as duas Organizations.",
    )
    roteiro.passo(
        "6",
        "Autoavaliacao contratual compartilhada (fornecedor)",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}/evaluate",
            {
                "subject_type": "ANIMAL",
                "subject_id": "validacao-sujeito-composicao",
                "purpose": _FINALIDADE,
                "reference_time": datetime.now(UTC).isoformat(),
            },
        ),
        201,
        guardar=lambda r: ids.update(evaluation_id=str(r["evaluation_id"])),
        porque="Compose-with-matrix parte de uma Evaluation contratual ja persistida.",
    )
    roteiro.passo(
        "7",
        "Comprador compoe com a matriz de elegibilidade (Fluxo B)",
        lambda: cliente.post(
            f"/v1/rule-governance/policies/shared-policies/{ids['policy_id']}/compose-with-matrix",
            {
                "grant_id": ids["grant_id"],
                "evaluation_id": ids["evaluation_id"],
                "market": _MERCADO,
            },
        ),
        201,
        conferir=lambda r: (
            None
            if set(r.corpo.keys()) == {"grant_id", "evaluation_id", "market", "composite_verdict"}
            else "resposta vazou campo alem do veredito composto"
        ),
        porque=(
            "A resposta nunca expoe rule_results de nenhum dos lados -- so o "
            "veredito composto (ADR-0066, risco 'composicao expoe matriz')."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(
        description="Roteiro de composicao com a matriz de elegibilidade regulatoria."
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
    print(f"{CINZA}  Rode seed/bootstrap novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(cliente, organizacao).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(
            f"{AMARELO}Sem regra de mercado adotada neste ambiente, o veredito composto "
            f"tende a REQUER_REVISAO -- o script confere forma e isolamento, a leitura "
            f"de negocio segue humana.{FIM}"
        )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
