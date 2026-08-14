"""Roteiro T-05D Corte 4: captura territorial sintética via API.

python -m uv run --locked python -m apps.validacao.captura_territorial_sintetica
python -m uv run --locked python -m apps.validacao.captura_territorial_sintetica --pausar
"""

import argparse
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, FIM, NEGRITO, Cliente, Requisicao, Roteiro

QUADRADO_MT = {
    "type": "Polygon",
    "coordinates": [
        [
            [-56.1, -15.8],
            [-56.0, -15.8],
            [-56.0, -15.7],
            [-56.1, -15.7],
            [-56.1, -15.8],
        ]
    ],
}


def _preflight(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        tabela = connection.execute(
            text("SELECT to_regclass('core_audit.territorial_source_captures')")
        ).scalar_one()
        if tabela is None:
            raise SystemExit(
                f"{AMARELO}A migration de capturas territoriais nao esta aplicada.{FIM}\n"
                "Execute: python -m uv run --locked alembic upgrade head"
            )
        permissao = connection.execute(
            text("SELECT 1 FROM core_identity.permissions WHERE code = :code"),
            {"code": "LIVESTOCK_TERRITORIAL_CAPTURE.SYNTHETIC_CREATE"},
        ).scalar_one_or_none()
        if permissao is None:
            raise SystemExit(
                f"{AMARELO}A permissao sintética ainda nao foi semeada.{FIM}\n"
                "Execute a seed e suba a API com a operadora nova desta execucao."
            )


def _roteiro(operador: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro(
        "T-05D Corte 4 - captura territorial sintetica via API",
        diario=operador.diario,
    )

    roteiro.passo(
        "1",
        "Cria propriedade fictícia",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"TERR-SYN-{uuid4().hex[:8]}",
                "name": "Fazenda Captura Territorial Sintetica",
                "municipality": "Cuiaba",
                "state_code": "MT",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(property_id=str(r["property_id"])),
        porque="O roteiro cria seu próprio alvo e não depende de UUID copiado manualmente.",
    )
    roteiro.passo(
        "2",
        "Registra geometria fictícia pela API existente",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/geometry",
            {"source": "DECLARADA", "geojson": QUADRADO_MT},
        ),
        201,
        conferir=lambda r: None if r["geometry_id"] and r["version"] == 1 else "sem geometria",
        guardar=lambda r: ids.update(
            geometry_id=str(r["geometry_id"]), geometry_version=str(r["version"])
        ),
        porque="A captura territorial sempre aponta para uma geometria já preservada.",
    )
    roteiro.passo(
        "3",
        "Registra captura FUNAI-like com sobreposição sintética",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-captures/synthetic",
            {
                "geometry_id": ids["geometry_id"],
                "geometry_version": int(ids["geometry_version"]),
                "profile": "FUNAI_LIKE_OVERLAP",
                "request_scope": {
                    "geometry_id": ids["geometry_id"],
                    "geometry_version": int(ids["geometry_version"]),
                    "layer": "FUNAI_LIKE",
                    "operation": "OVERLAP",
                },
                "response_payload": {
                    "feature_count": 1,
                    "property_area_hectares": 1000.0,
                    "overlap_area_hectares": 42.0,
                    "source_version_ids": ["FUNAI_TEST_2026_V1"],
                },
                "captured_at": "2026-03-01T00:00:00Z",
                "known_at": "2026-03-02T00:00:00Z",
                "source_valid_from": None,
                "source_valid_to": None,
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["source_profile_code"] == "TERRITORIAL_TEST_SOURCE"
            and r["response_summary"]["profile"] == "FUNAI_LIKE_OVERLAP"
            and "NO_EXTERNAL_RECOGNITION_ASSERTED" in r["limitations"]
            and "response_payload" not in r.corpo
            else "captura overlap nao preservou a fronteira sintética esperada"
        ),
        guardar=lambda r: ids.update(overlap_digest=str(r["response_digest"])),
        porque=(
            "A API preserva material sintético; não consulta FUNAI real nem decide conformidade."
        ),
    )
    roteiro.passo(
        "4",
        "Registra captura PRODES-like timeline",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-captures/synthetic",
            {
                "geometry_id": ids["geometry_id"],
                "geometry_version": int(ids["geometry_version"]),
                "profile": "PRODES_LIKE_TIMELINE",
                "request_scope": {"layer": "PRODES_LIKE", "operation": "TIMELINE"},
                "response_payload": {
                    "property_area_hectares": 1000.0,
                    "years": [
                        {
                            "year": 2024,
                            "feature_count": 1,
                            "source_area_hectares": 12.5,
                            "overlap_area_hectares": 4.2,
                            "source_version_ids": ["PRODES_TEST_2024_V1"],
                        }
                    ],
                },
                "captured_at": "2026-03-01T00:00:00Z",
                "known_at": "2026-03-02T00:00:00Z",
                "source_valid_from": "2024-01-01T00:00:00Z",
                "source_valid_to": "2025-01-01T00:00:00Z",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["response_summary"]["profile"] == "PRODES_LIKE_TIMELINE"
            and r["source_version_ids"] == ["PRODES_TEST_2024_V1"]
            else "captura timeline nao preservou versao declarada"
        ),
        porque="Timeline e overlap são materiais diferentes, mas ambos entram pelo mesmo contrato.",
    )
    roteiro.passo(
        "5",
        "Lista as capturas territoriais sintéticas da propriedade",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-captures?limit=50&offset=0"
        ),
        200,
        conferir=lambda r: (
            None
            if len(r["items"]) == 2
            and all("response_payload" not in item for item in r["items"])
            and ids["overlap_digest"] in {str(item["response_digest"]) for item in r["items"]}
            else "listagem nao retornou as duas capturas sem payload bruto"
        ),
        porque="A leitura devolve metadados e resumo estruturado, não material bruto externo.",
    )
    roteiro.passo(
        "6",
        "Recusa versão de geometria divergente",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-captures/synthetic",
            {
                "geometry_id": ids["geometry_id"],
                "geometry_version": 999,
                "profile": "FUNAI_LIKE_OVERLAP",
                "request_scope": {"layer": "FUNAI_LIKE", "operation": "OVERLAP"},
                "response_payload": {"feature_count": 0},
                "captured_at": "2026-03-01T00:00:00Z",
                "known_at": "2026-03-02T00:00:00Z",
            },
        ),
        409,
        conferir=lambda r: (
            None
            if r["reason_code"] == "CONFLITO_DE_REFERENCIA"
            else "versao divergente nao retornou conflito de referencia"
        ),
        porque="Versão divergente é conflito com uma referência existente, não captura nova.",
    )
    roteiro.passo(
        "7",
        "Confirma que não houve conclusão normativa",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-captures?limit=50&offset=0"
        ),
        200,
        conferir=lambda r: (
            None
            if len(r["items"]) == 2
            and all(item["source_environment"] == "SYNTHETIC" for item in r["items"])
            else "estado final inesperado para capturas sintéticas"
        ),
        porque=(
            "O roteiro termina lembrando a fronteira: nenhuma Policy, Evaluation, "
            "Decision, Dossier ou autorização externa foi criada."
        ),
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida captura territorial sintética.")
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    options = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = _ambiente("TITAN_DATABASE_URL", "")
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL antes do roteiro.")
    _preflight(database_url)
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
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_operador",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organization,
        rotulo="operador",
        diario=diary,
    )
    print(
        f"{NEGRITO}Preflight{FIM}\n"
        f"  API: {api}\n"
        f"  Keycloak: {keycloak}\n"
        f"  Organization: {organization}\n"
        "  Fonte: TERRITORIAL_TEST_SOURCE / SYNTHETIC"
    )
    return _roteiro(operator).executar(pausar=options.pausar)


if __name__ == "__main__":
    raise SystemExit(main())
