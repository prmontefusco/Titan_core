"""Roteiro executavel da leitura territorial FUNAI via HTTP real.

python -m uv run --locked python -m apps.validacao.funai
python -m uv run --locked python -m apps.validacao.funai --pausar
"""

import argparse
import sys
from datetime import UTC, datetime

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro

QUADRADO_MS = {
    "type": "Polygon",
    "coordinates": [
        [
            [-54.0, -22.0],
            [-54.0, -21.0],
            [-53.0, -21.0],
            [-53.0, -22.0],
            [-54.0, -22.0],
        ]
    ],
}


def _exigir_provider_configurado(operador: Cliente) -> None:
    inexistente = "00000000-0000-4000-8000-000000000000"
    resposta = operador.get(f"/v1/livestock/properties/{inexistente}/territorial-overlaps/funai")
    if resposta.status == 503 and resposta.corpo.get("reason_code") == "PROVIDER_NAO_CONFIGURADO":
        raise SystemExit(
            f"{AMARELO}O provider Titan_geodata nao esta configurado na API atual.{FIM}\n"
            "Defina TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY no ambiente da API,\n"
            "reinicie o servidor e rode este roteiro de novo."
        )


def _exigir_referencia_externa() -> tuple[str, str]:
    cod_imovel = _ambiente("TITAN_VALIDACAO_FUNAI_COD_IMOVEL", "").strip()
    state = _ambiente("TITAN_VALIDACAO_FUNAI_STATE", "MS").strip().upper()
    if not cod_imovel:
        raise SystemExit(
            f"{AMARELO}Defina TITAN_VALIDACAO_FUNAI_COD_IMOVEL antes de rodar este roteiro.{FIM}\n"
            "Use um cod_imovel real do provider cuja leitura territorial voce queira validar.\n"
            "Exemplo:\n"
            '$env:TITAN_VALIDACAO_FUNAI_COD_IMOVEL="MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E"'
        )
    if len(state) != 2:
        raise SystemExit("TITAN_VALIDACAO_FUNAI_STATE deve ter duas letras.")
    return cod_imovel, state


def _montar_roteiro(operador: Cliente, auditor: Cliente, *, cod_imovel: str, state: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Leitura territorial da FUNAI via HTTP real", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cria a propriedade da validacao",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"FUNAI-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
                "name": "Fazenda de validacao FUNAI",
                "municipality": "Dourados",
                "state_code": state,
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(property_id=str(r["property_id"])),
        porque="O roteiro cria o proprio alvo e nao depende de identificadores copiados a mao.",
    )
    roteiro.passo(
        "2",
        "Operador registra a geometria vigente com referencia externa do CAR",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/geometry",
            {
                "source": "SICAR_CAR",
                "external_reference": cod_imovel,
                "geojson": QUADRADO_MS,
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["geometry_id"]
            and r["source"] == "SICAR_CAR"
            and r["external_reference"] == cod_imovel
            else "geometria nao preservou a referencia externa esperada"
        ),
        guardar=lambda r: ids.update(geometry_id=str(r["geometry_id"])),
        porque=(
            "A leitura FUNAI usa a geometria vigente e a referencia externa do CAR; "
            "sem essa referencia a consulta precisa declarar lacuna."
        ),
    )
    roteiro.passo(
        "3",
        "Operador consulta a sobreposicao territorial FUNAI",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-overlaps/funai"
        ),
        200,
        conferir=lambda r: (
            None
            if r["property_id"] == ids["property_id"]
            and r["layer"] == "FUNAI_TI"
            and r["source"] == "FUNAI"
            and isinstance(r["version_ids"], list)
            and isinstance(r["gaps"], list)
            else "consulta nao trouxe a forma esperada para a leitura territorial FUNAI"
        ),
        guardar=lambda r: ids.update(
            status=str(r["status"]),
            feature_count=str(r["feature_count"]),
        ),
        porque=(
            "Esta chamada responde o que o provider territorial declara agora sobre a "
            "camada FUNAI_TI para o cod_imovel informado."
        ),
    )
    roteiro.passo(
        "4",
        "Auditor tambem consegue ler a consulta territorial",
        lambda: auditor.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-overlaps/funai"
        ),
        200,
        conferir=lambda r: (
            None
            if r["status"] == ids["status"] and str(r["feature_count"]) == ids["feature_count"]
            else "leitura do auditor divergiu da observacao do operador nesta execucao"
        ),
        porque=(
            "A consulta territorial e leitura tecnica; auditor pode ler o mesmo material, "
            "sem precisar de permissao de escrita."
        ),
    )
    roteiro.passo(
        "5",
        "Operador consulta o catalogo governavel da vertical",
        lambda: operador.get("/v1/rule-governance/catalogs/livestock-market-rules"),
        200,
        conferir=lambda r: (
            None
            if any(
                item.get("fact_type") == "livestock.territorial.funai"
                for item in r["fact_types"]
            )
            and any(
                item.get("rule_code") == "rule-sobreposicao-funai"
                for item in r["templates"]
            )
            else "catalogo nao publicou o fato ou o template governavel da FUNAI"
        ),
        porque=(
            "O fechamento operacional inclui a trilha governavel: a leitura tecnica esta "
            "pronta e a regra correspondente ja e publicavel por governanca."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da leitura territorial FUNAI.")
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
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL para o roteiro descobrir a Organization.")
    cod_imovel, state = _exigir_referencia_externa()

    admin = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    operador_subject = admin.garantir_usuario(
        username="titan_operador",
        senha=SENHA_DEMONSTRACAO,
    )
    admin.garantir_usuario(username="titan_auditor", senha=SENHA_DEMONSTRACAO)
    issuer = f"{keycloak_url}/realms/{realm}"
    organizacao = opcoes.organizacao or _descobrir_organizacao(
        database_url,
        issuer=issuer,
        subject=operador_subject,
    )
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
    auditor = Cliente(
        base_url=api,
        token=admin.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO,
            username="titan_auditor",
            senha=SENHA_DEMONSTRACAO,
        ),
        organization_id=organizacao,
        rotulo="auditor",
        diario=diario,
    )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API          : {api}")
    print(f"  Keycloak     : {keycloak_url} (realm {realm})")
    print(f"  Organization : {organizacao}")
    print(f"  Cod. imovel  : {cod_imovel}")
    print(
        f"{CINZA}  Este roteiro depende do Titan_geodata configurado na API "
        f"(TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY).{FIM}"
    )

    _exigir_provider_configurado(operador)

    codigo = _montar_roteiro(
        operador,
        auditor,
        cod_imovel=cod_imovel,
        state=state,
    ).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(
            f"{AMARELO}O script confere forma e status; a decisao de mercado que usa "
            f"FUNAI ainda depende de adocao normativa explicita.{FIM}"
        )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
