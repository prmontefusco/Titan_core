"""Roteiro executável para validar `GET /v1/asset/part-applicability`.

python -m uv run --locked python -m apps.validacao.asset.part_applicability
python -m uv run --locked python -m apps.validacao.asset.part_applicability --pausar

O roteiro não pede identificadores manualmente: descobre a Organization do
usuário de validação e uma combinação Part + Vehicle coberta por uma
Applicability ASSERTED no banco local.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from urllib.parse import urlencode

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro


def _instant_utc(value: datetime) -> str:
    instant = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _descobrir_alvo(database_url: str, organizacao: str) -> tuple[str, str, str]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT a.part_id, v.vehicle_id, a.target_valid_from "
                    "FROM core_audit.applicability a "
                    "JOIN core_audit.vehicles v "
                    "ON v.record_owner_organization_id = a.record_owner_organization_id "
                    "AND v.model_id = a.target_model_id "
                    "AND ("
                    "  (v.variant_id IS NULL AND a.target_variant_id IS NULL) "
                    "  OR v.variant_id = a.target_variant_id"
                    ") "
                    "AND (a.target_serial_from IS NULL OR v.serial_number >= a.target_serial_from) "
                    "AND (a.target_serial_to IS NULL OR v.serial_number <= a.target_serial_to) "
                    "WHERE a.record_owner_organization_id = :organization_id "
                    "AND a.state = 'ASSERTED' "
                    "ORDER BY a.asserted_at ASC, a.applicability_id ASC LIMIT 1"
                ),
                {"organization_id": organizacao},
            ).fetchone()
    finally:
        engine.dispose()
    if row is None:
        raise SystemExit(
            "Nenhuma Applicability ASSERTED com Vehicle compatível foi encontrada para esta "
            "Organization. Rode a semeadura/fixture Asset antes de validar aplicabilidade."
        )
    return str(row[0]), str(row[1]), _instant_utc(row[2])


def _applicability_path(part_id: str, vehicle_id: str, instant: str) -> str:
    query = urlencode({"part_id": part_id, "vehicle_id": vehicle_id, "instant": instant})
    return f"/v1/asset/part-applicability?{query}"


def _exigir_permissao_applicability_read(
    cliente: Cliente, part_id: str, vehicle_id: str, instant: str
) -> None:
    sonda = cliente.get(_applicability_path(part_id, vehicle_id, instant))
    if sonda.status != 403:
        return
    reason = sonda.corpo.get("reason_code") if isinstance(sonda.corpo, dict) else None
    if reason == "PERMISSAO_AUSENTE":
        raise SystemExit(
            f"{AMARELO}O usuário de validação não possui ASSET_APPLICABILITY.READ.{FIM}\n"
            "Papéis guardam as permissões existentes quando foram criados. "
            "Semeie novamente com as permissões Asset e reinicie a API."
        )


def _montar_roteiro(cliente: Cliente, part_id: str, vehicle_id: str, instant: str) -> Roteiro:
    roteiro = Roteiro("Asset A5 — Part Applicability", diario=cliente.diario)
    roteiro.passo(
        "1",
        "Resolver aplicabilidade de peça para veículo",
        lambda: cliente.get(_applicability_path(part_id, vehicle_id, instant)),
        200,
        conferir=lambda r: (
            None
            if r["part_ref"] == part_id
            and r["vehicle_id"] == vehicle_id
            and isinstance(r["assertions"], list)
            and all("evidence_ref" in item for item in r["assertions"])
            else "resposta não preservou part_ref, vehicle_id, assertions ou evidence_ref"
        ),
        porque=(
            "Confirma que A5 expõe as asserções de aplicabilidade sem reduzi-las "
            "a um booleano sem evidência."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Roteiro Asset A5 — Part Applicability.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument(
        "--organizacao", default="", help="Organization do teste. Sem isto, descobre pelo vínculo."
    )
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir Organization e Applicability.")

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    subject = admin.garantir_usuario(username="titan_operador", senha=SENHA_DEMONSTRACAO)
    issuer = f"{keycloak_url}/realms/{realm}"
    organizacao = args.organizacao or _descobrir_organizacao(
        database_url, issuer=issuer, subject=subject
    )
    part_id, vehicle_id, instant = _descobrir_alvo(database_url, organizacao)

    diario: list[Requisicao] = []
    operador = Cliente(
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
    print(f"  Part         : {part_id}")
    print(f"  Vehicle      : {vehicle_id}")
    print(f"  Instant      : {instant}")
    print(
        f"{CINZA}  Organization, Part, Vehicle e instant foram descobertos; "
        f"nada foi copiado à mão.{FIM}"
    )

    _exigir_permissao_applicability_read(operador, part_id, vehicle_id, instant)
    code = _montar_roteiro(operador, part_id, vehicle_id, instant).executar(pausar=args.pausar)
    if code == 0:
        print(f"{AMARELO}O script confere forma e status; o julgamento de negócio é humano.{FIM}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
