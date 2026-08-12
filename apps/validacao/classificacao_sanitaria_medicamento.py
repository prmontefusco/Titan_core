"""Roteiro ADR-0056: classificação sanitária versionada de medicamento."""

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import FIM, NEGRITO, Cliente, Requisicao, Resposta, Roteiro


def roteiro(client: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    flow = Roteiro("ADR-0056 - classificação sanitária", diario=client.diario)

    def create_medication() -> Resposta:
        response = client.post(
            "/v1/livestock/medications",
            {
                "trade_name": f"MED-{uuid4().hex[:8]}",
                "active_ingredient": "Ingrediente fictício",
                "manufacturer": "Laboratório fictício",
                "withdrawal_period_days": 10,
            },
        )
        if response.status == 201:
            ids["medication"] = str(response["medication_id"])
        return response

    flow.passo(
        "1",
        "Cria medicamento farmacológico sem inferência sanitária",
        create_medication,
        201,
        porque="PHARMACOLOGICAL não implica ANTIMICROBIAL.",
    )
    flow.passo(
        "2",
        "Confirma ausência de Assertion",
        lambda: client.get(
            f"/v1/livestock/medications/{ids['medication']}/sanitary-classifications"
        ),
        200,
        conferir=lambda r: None if r == [] else "esperava NO_ASSERTION",
        porque="NO_ASSERTION deve permanecer distinto de UNKNOWN.",
    )
    flow.passo(
        "3",
        "Registra UNKNOWN auditável",
        lambda: client.post(
            f"/v1/livestock/medications/{ids['medication']}/sanitary-classifications",
            {
                "status": "UNKNOWN",
                "observed_at": datetime.now(UTC).isoformat(),
                "limitations": ["CLASSIFICACAO_NAO_DETERMINADA"],
            },
        ),
        201,
        porque="Uma fonte pode afirmar indeterminação sem produzir negação.",
    )
    return flow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    options = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL antes do roteiro.")
    organization = options.organizacao or _descobrir_organizacao(database_url)
    admin = AdminKeycloak.autenticar(
        base_url=keycloak,
        realm=_ambiente("TITAN_OIDC_REALM", "titan"),
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diary: list[Requisicao] = []
    client = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO, username="titan_operador", senha=SENHA_DEMONSTRACAO
        ),
        organization_id=organization,
        rotulo="operador",
        diario=diary,
    )
    print(f"{NEGRITO}Preflight{FIM}\n  API: {api}\n  Keycloak: {keycloak}")
    print(f"  Organization: {organization}")
    return roteiro(client).executar(pausar=options.pausar)


if __name__ == "__main__":
    raise SystemExit(main())
