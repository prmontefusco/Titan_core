"""Roteiro executavel de prescricao veterinaria (NR-4).

python -m uv run --locked python -m apps.validacao.prescricao_veterinaria
python -m uv run --locked python -m apps.validacao.prescricao_veterinaria --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime
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


def _montar_roteiro(operador: Cliente, auditor: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("NR-4 - Prescricao veterinaria operavel pela API", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador encontra uma propriedade da Organization",
        lambda: operador.get("/v1/livestock/properties?limit=1"),
        200,
        conferir=lambda r: None if r["items"] else "nenhuma propriedade disponivel",
        guardar=lambda r: ids.update(property_id=str(r["items"][0]["property_id"])),
        porque="Nenhum identificador e copiado a mao; a prescricao precisa de uma propriedade.",
    )
    roteiro.passo(
        "2",
        "Operador cria animal, medicamento e veterinario documentado",
        lambda: _criar_base(operador, ids),
        201,
        conferir=lambda r: (
            None if r["verification_status"] == "DOCUMENTADO" else "veterinario nao foi documentado"
        ),
        porque="A emissao exige veterinario DOCUMENTADO ou VERIFICADO_EM_FONTE.",
    )
    roteiro.passo(
        "3",
        "Operador emite uma prescricao para o animal",
        lambda: operador.post(
            "/v1/livestock/prescriptions",
            {
                "veterinarian_id": ids["veterinarian_id"],
                "medication_id": ids["medication_id"],
                "property_id": ids["property_id"],
                "dosage": "1 mL",
                "administration_route": "subcutanea",
                "target_type": "ANIMAL",
                "target_ids": [ids["animal_id"]],
                "reason": "Validacao ficticia da prescricao.",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["target_ids"] == [ids["animal_id"]]
            and r["veterinarian_id"] == ids["veterinarian_id"]
            and r["administration_route"] == "SUBCUTANEA"
            else "prescricao nao preservou alvo, veterinario ou via"
        ),
        guardar=lambda r: ids.update(prescription_id=str(r["prescription_id"])),
        porque="A prescricao vira registro proprio antes de ser exigida por regra.",
    )
    roteiro.passo(
        "4",
        "Operador detalha a prescricao emitida",
        lambda: operador.get(f"/v1/livestock/prescriptions/{ids['prescription_id']}"),
        200,
        conferir=lambda r: (
            None
            if r["prescription_id"] == ids["prescription_id"]
            and r["medication_id"] == ids["medication_id"]
            else "detalhe nao retornou a prescricao esperada"
        ),
        porque="O identificador salvo precisa levar ao mesmo registro auditavel.",
    )
    roteiro.passo(
        "5",
        "Auditor nao emite prescricao",
        lambda: auditor.post("/v1/livestock/prescriptions", {}),
        403,
        conferir=lambda r: (
            None if r["reason_code"] == "PERMISSAO_AUSENTE" else "negacao inesperada"
        ),
        porque="Ler a cadeia nao concede autoridade para criar registro veterinario.",
    )
    return roteiro


def _criar_base(operador: Cliente, ids: dict[str, str]) -> Resposta:
    animal = operador.post(
        "/v1/livestock/animals",
        {
            "birth_property_id": ids["property_id"],
            "sex": "FEMALE",
        },
    )
    ids["animal_id"] = str(animal["animal_id"])
    medicamento = operador.post(
        "/v1/livestock/medications",
        {
            "trade_name": f"PrescMed-{uuid4().hex[:8]}",
            "active_ingredient": "Produto ficticio",
            "manufacturer": "Fabricante ficticio",
            "withdrawal_period_days": 7,
        },
    )
    ids["medication_id"] = str(medicamento["medication_id"])
    veterinario = operador.post(
        "/v1/livestock/veterinarians",
        {
            "name": "Dra. Validacao",
            "cpf": f"{datetime.now(UTC).timestamp():.0f}".zfill(11)[-11:],
            "council_number": f"CRMV-{uuid4().hex[:8]}",
            "council_state": "MT",
        },
    )
    ids["veterinarian_id"] = str(veterinario["veterinarian_id"])
    return operador.post(
        f"/v1/livestock/veterinarians/{ids['veterinarian_id']}/verification",
        {"new_status": "DOCUMENTADO"},
    )


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da NR-4.")
    argumentos.add_argument("--pausar", action="store_true")
    argumentos.add_argument("--organizacao", default="")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para descobrir a Organization.")
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diario: list[Requisicao] = []

    def cliente(username: str, rotulo: str) -> Cliente:
        return Cliente(
            base_url=api,
            token=admin.token_de_usuario(
                client_id=CLIENTE_DE_VALIDACAO,
                username=username,
                senha=SENHA_DEMONSTRACAO,
            ),
            organization_id=organizacao,
            rotulo=rotulo,
            diario=diario,
        )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(
        cliente("titan_operador", "operador"),
        cliente("titan_auditor", "auditor"),
    ).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
