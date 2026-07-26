"""Roteiro executavel da exigibilidade sanitaria minima (Passo 14.3).

python -m uv run --locked python -m apps.validacao.exigibilidade_sanitaria_minima
python -m uv run --locked python -m apps.validacao.exigibilidade_sanitaria_minima --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
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


def _montar_roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Passo 14.3 - Exigibilidade sanitaria minima", diario=operador.diario)
    codigo_campanha = f"PNCEBT-BRUCELOSE-{uuid4().hex[:8]}"

    roteiro.passo(
        "1",
        "Operador encontra uma propriedade da Organization",
        lambda: operador.get("/v1/livestock/properties?limit=1"),
        200,
        conferir=lambda r: None if r["items"] else "nenhuma propriedade disponivel",
        guardar=lambda r: ids.update(property_id=str(r["items"][0]["property_id"])),
        porque="O roteiro descobre onde criar o animal; nenhum identificador e copiado a mao.",
    )
    roteiro.passo(
        "2",
        "Operador cria animal, campanha, medicamento, lote e aplicacao vinculada",
        lambda: _criar_cenario(operador, ids, codigo_campanha),
        201,
        conferir=lambda r: (
            None
            if r["sanitary_campaign_id"] == ids["campaign_id"]
            else "tratamento nao retornou vinculo com a campanha"
        ),
        porque="A exigibilidade precisa de uma campanha declarada e uma aplicacao efetiva.",
    )
    roteiro.passo(
        "3",
        "Operador consulta a exigibilidade sanitaria da campanha",
        lambda: operador.get(
            f"/v1/livestock/animals/{ids['animal_id']}/sanitary-requirements/{codigo_campanha}"
        ),
        200,
        conferir=lambda r: (
            None
            if r["status"] == "ATENDIDA"
            and r["campaign_id"] == ids["campaign_id"]
            and r["application_id"] == ids["application_id"]
            and r["gaps"] == []
            else "exigibilidade nao declarou a campanha atendida"
        ),
        porque="A leitura deve responder com status, vinculos e lacunas, nao com texto livre.",
    )
    roteiro.passo(
        "4",
        "Operador consulta uma campanha exigida ainda nao declarada",
        lambda: operador.get(
            f"/v1/livestock/animals/{ids['animal_id']}/sanitary-requirements/"
            f"campanha-inexistente-{uuid4().hex[:8]}"
        ),
        200,
        conferir=lambda r: (
            None
            if r["status"] == "INDETERMINADA"
            and r["campaign_id"] is None
            and r["gaps"][0]["code"] == "CAMPANHA_NAO_DECLARADA"
            else "campanha nao declarada nao virou lacuna indeterminada"
        ),
        porque="Ausencia de regra/campanha declarada nao pode virar aprovacao nem reprovacao.",
    )
    return roteiro


def _criar_cenario(
    operador: Cliente,
    ids: dict[str, str],
    codigo_campanha: str,
) -> Resposta:
    agora = datetime.now(UTC)
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
            "trade_name": f"Vacina-{uuid4().hex[:8]}",
            "active_ingredient": "Antigeno inativado ficticio",
            "manufacturer": "Fabricante ficticio",
            "withdrawal_period_days": 0,
            "product_class": "IMMUNOBIOLOGICAL",
        },
    )
    lote = operador.post(
        "/v1/livestock/medication-batches",
        {
            "medication_id": medicamento["medication_id"],
            "batch_number": f"LOTE-{uuid4().hex[:8]}",
            "expiry_date": (agora + timedelta(days=365)).isoformat(),
        },
    )
    campanha = operador.post(
        "/v1/livestock/sanitary-campaigns",
        {
            "code": codigo_campanha,
            "name": "Campanha ficticia de brucelose",
            "starts_at": (agora - timedelta(days=30)).isoformat(),
            "ends_at": (agora + timedelta(days=30)).isoformat(),
            "disease": "Brucelose",
            "authority": "Autoridade ficticia",
        },
    )
    ids["campaign_id"] = str(campanha["campaign_id"])
    tratamento = operador.post(
        "/v1/livestock/treatments",
        {
            "animal_id": ids["animal_id"],
            "medication_batch_id": lote["batch_id"],
            "applied_at": agora.isoformat(),
            "dose": "2 mL",
            "sanitary_campaign_id": ids["campaign_id"],
        },
    )
    ids["application_id"] = str(tratamento["application_id"])
    return tratamento


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do Passo 14.3.")
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
    print(f"{CINZA}  Rode a semeadura novamente se vier 403 por permissao ausente.{FIM}")

    codigo = _montar_roteiro(operador).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
