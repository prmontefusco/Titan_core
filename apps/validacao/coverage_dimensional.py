"""Roteiro NEXT-01: importação source-neutral de coverage dimensional.

python -m uv run --locked python -m apps.validacao.coverage_dimensional [--pausar]
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("NEXT-01 - Coverage dimensional source-neutral", diario=operador.diario)

    def criar_animal() -> object:
        prop = operador.post(
            "/v1/livestock/properties",
            {
                "code": f"COV-{uuid4().hex[:8]}",
                "name": "Fazenda Coverage Fictícia",
                "municipality": "Cuiaba",
                "state_code": "MT",
            },
        )
        if prop.status != 201:
            return prop
        animal = operador.post(
            "/v1/livestock/animals", {"birth_property_id": prop["property_id"], "sex": "FEMALE"}
        )
        if animal.status == 201:
            ids["animal_id"] = str(animal["animal_id"])
        return animal

    roteiro.passo(
        "1",
        "Cria Animal fictício",
        criar_animal,
        201,
        conferir=lambda r: None if ids.get("animal_id") else "animal não descoberto",
        porque="A contribuição deve ser isolada por Organization e Subject real.",
    )
    end = datetime.now(UTC)
    roteiro.passo(
        "2",
        "Importa contribuição sem artefato obrigatório",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/coverage-contributions",
            {
                "dimension": "treatment_history",
                "covered_from": (end - timedelta(days=45)).isoformat(),
                "covered_until": end.isoformat(),
                "validation": "VALIDATED",
                "admissibility": "ADMISSIBLE",
                "accessible": True,
                "conflicting": False,
            },
        ),
        201,
        conferir=lambda r: (
            None if r["source_id"] is None else "fonte neutra ganhou artefato implícito"
        ),
        guardar=lambda r: ids.update(contribution_id=str(r["contribution_id"])),
        porque="Prova que ReceivedTransferArtifact não é requisito nem dono da coverage.",
    )
    roteiro.passo(
        "3",
        "Lista e reencontra a contribuição",
        lambda: operador.get(f"/v1/livestock/animals/{ids['animal_id']}/coverage-contributions"),
        200,
        conferir=lambda r: (
            None
            if r["items"][0]["contribution_id"] == ids["contribution_id"]
            else "contribuição não persistida"
        ),
        porque="A auditoria precisa recuperar dimensão, intervalo, validation e admissibility.",
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida coverage dimensional do NEXT-01.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    options = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL antes do roteiro.")
    organization = options.organizacao or _descobrir_organizacao(database_url)
    admin = AdminKeycloak.autenticar(
        base_url=keycloak,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diary: list[Requisicao] = []
    operator = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO, username="titan_operador", senha=SENHA_DEMONSTRACAO
        ),
        organization_id=organization,
        rotulo="operador",
        diario=diary,
    )
    print(
        f"{NEGRITO}Preflight{FIM}\n"
        f"  API: {api}\n  Keycloak: {keycloak}\n  Organization: {organization}"
    )
    return _roteiro(operator).executar(pausar=options.pausar)


if __name__ == "__main__":
    raise SystemExit(main())
