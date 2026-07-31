"""Acrescenta o campo "tipo de entidade" ao cadastro do Keycloak local.

Não concede nada por si só (ADR-0031: sem autoatribuição) — é só uma
conveniência de UX. O valor escolhido no cadastro chega ao frontend como claim
do ID Token e pré-seleciona o formulário do pedido real de EntityTypeRequest,
que continua exigindo aprovação de um admin da Organization.

Idempotente: reexecutar não duplica o atributo nem o mapeador.

python -m uv run --locked python -m apps.keycloak_profile_setup
"""

import os

from apps.seed.keycloak import AdminKeycloak
from packages.livestock_domain.entity_type_request import EntityKind

ATRIBUTO = "titan_requested_kind"
CLAIM = "titan_requested_kind"
CLIENT_ID = "titan-web"

ROTULOS = {
    EntityKind.ADMIN: "Administrador",
    EntityKind.PRODUTOR: "Produtor (e funcionários)",
    EntityKind.FRIGORIFICO: "Frigorífico",
    EntityKind.VETERINARIO: "Veterinário",
    EntityKind.AUDITOR: "Auditor",
    EntityKind.CERTIFICADOR: "Certificador",
    EntityKind.CONSUMIDOR: "Consumidor",
}


def _ambiente(nome: str, padrao: str) -> str:
    return os.environ.get(nome, "").strip() or padrao


def main() -> None:
    if os.environ.get("TITAN_KEYCLOAK_PROFILE_SETUP_CONFIRM") != "1":
        raise SystemExit(
            "Altera o realm do Keycloak (perfil de registro e client titan-web). "
            "Confirme com TITAN_KEYCLOAK_PROFILE_SETUP_CONFIRM=1."
        )

    base_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    admin = AdminKeycloak.autenticar(
        base_url=base_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )

    admin.garantir_atributo_de_perfil_select(
        nome=ATRIBUTO,
        rotulo="Tipo de entidade",
        opcoes=[kind.value for kind in EntityKind],
        rotulos_das_opcoes={kind.value: rotulo for kind, rotulo in ROTULOS.items()},
    )
    admin.garantir_mapeador_de_atributo_no_id_token(
        CLIENT_ID, nome_atributo=ATRIBUTO, nome_claim=CLAIM
    )
    print(
        f"Atributo '{ATRIBUTO}' e mapeador do client '{CLIENT_ID}' garantidos no realm '{realm}'."
    )


if __name__ == "__main__":
    main()
