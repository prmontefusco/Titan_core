"""Roteiro executavel das timelines territoriais PRODES e DETER via HTTP real.

python -m uv run --locked python -m apps.validacao.timelines_territoriais
python -m uv run --locked python -m apps.validacao.timelines_territoriais --pausar
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
    resposta = operador.get(
        f"/v1/livestock/properties/{inexistente}/territorial-timelines/prodes?year_from=2020&year_to=2021"
    )
    if resposta.status == 503 and resposta.corpo.get("reason_code") == "PROVIDER_NAO_CONFIGURADO":
        raise SystemExit(
            f"{AMARELO}O provider Titan_geodata nao esta configurado na API atual.{FIM}\n"
            "Defina TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY no ambiente da API,\n"
            "reinicie o servidor e rode este roteiro de novo."
        )


def _exigir_referencia_externa() -> tuple[str, str]:
    cod_imovel = _ambiente("TITAN_VALIDACAO_TIMELINE_COD_IMOVEL", "").strip()
    state = _ambiente("TITAN_VALIDACAO_TIMELINE_STATE", "MS").strip().upper()
    if not cod_imovel:
        raise SystemExit(
            f"{AMARELO}Defina TITAN_VALIDACAO_TIMELINE_COD_IMOVEL "
            f"antes de rodar este roteiro.{FIM}\n"
            "Use um cod_imovel real do provider cuja serie temporal voce queira validar.\n"
            "Exemplo:\n"
            '$env:TITAN_VALIDACAO_TIMELINE_COD_IMOVEL="MS-5006606-3DCF573FEF1E44B9972057BD4C932A9E"'
        )
    if len(state) != 2:
        raise SystemExit("TITAN_VALIDACAO_TIMELINE_STATE deve ter duas letras.")
    return cod_imovel, state


def _montar_roteiro(
    operador: Cliente,
    auditor: Cliente,
    *,
    cod_imovel: str,
    state: str,
    prodes_year_from: int,
    prodes_year_to: int,
    deter_year_from: int,
    deter_year_to: int,
) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro(
        "Leitura territorial temporal PRODES/DETER via HTTP real",
        diario=operador.diario,
    )

    roteiro.passo(
        "1",
        "Operador cria a propriedade da validacao",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"TIMELINE-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
                "name": "Fazenda de validacao timeline territorial",
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
        porque=(
            "As leituras temporais reutilizam a geometria vigente e o cod_imovel do CAR; "
            "sem isso a consulta precisa declarar lacuna."
        ),
    )
    roteiro.passo(
        "3",
        "Operador consulta a timeline territorial PRODES",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-timelines/prodes"
            f"?year_from={prodes_year_from}&year_to={prodes_year_to}"
        ),
        200,
        conferir=lambda r: (
            None
            if r["property_id"] == ids["property_id"]
            and r["layer"] == "TB_PRODES"
            and r["status"] in {"DISPONIVEL", "INDETERMINADA"}
            and isinstance(r["years"], list)
            and isinstance(r["gaps"], list)
            else "consulta PRODES nao trouxe a forma esperada"
        ),
        guardar=lambda r: ids.update(prodes_status=str(r["status"])),
        porque=(
            "Esta chamada devolve a serie temporal declarada pelo provider para TB_PRODES, "
            "sem ainda decidir conformidade."
        ),
    )
    roteiro.passo(
        "4",
        "Operador consulta a timeline territorial DETER",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-timelines/deter"
            f"?year_from={deter_year_from}&year_to={deter_year_to}"
        ),
        200,
        conferir=lambda r: (
            None
            if r["property_id"] == ids["property_id"]
            and r["layer"] == "TB_DETER"
            and r["status"] in {"DISPONIVEL", "INDETERMINADA"}
            and isinstance(r["years"], list)
            and isinstance(r["gaps"], list)
            else "consulta DETER nao trouxe a forma esperada"
        ),
        guardar=lambda r: ids.update(deter_status=str(r["status"])),
        porque=(
            "DETER e outra camada, com outra semantica temporal; o roteiro valida que ela "
            "permanece separada do PRODES."
        ),
    )
    roteiro.passo(
        "5",
        "Auditor tambem consegue ler a timeline PRODES",
        lambda: auditor.get(
            f"/v1/livestock/properties/{ids['property_id']}/territorial-timelines/prodes"
            f"?year_from={prodes_year_from}&year_to={prodes_year_to}"
        ),
        200,
        conferir=lambda r: (
            None
            if r["status"] == ids["prodes_status"] and r["layer"] == "TB_PRODES"
            else "leitura do auditor divergiu da observacao PRODES desta execucao"
        ),
        porque=(
            "A timeline territorial e leitura tecnica: auditor pode reler a mesma projecao "
            "sem permissao de escrita."
        ),
    )
    roteiro.passo(
        "6",
        "Operador consulta o catalogo governavel da vertical",
        lambda: operador.get("/v1/rule-governance/catalogs/livestock-market-rules"),
        200,
        conferir=lambda r: (
            None
            if {"livestock.territorial.prodes", "livestock.territorial.deter"}.issubset(
                {item.get("fact_type") for item in r["fact_types"]}
            )
            and {"rule-desmatamento-prodes", "rule-alerta-deter"}.issubset(
                {item.get("rule_code") for item in r["templates"]}
            )
            else "catalogo nao publicou os fatos ou templates governaveis territoriais"
        ),
        porque=(
            "O fechamento operacional inclui a trilha governavel: as leituras tecnicas estao "
            "prontas e as regras correspondentes ja sao publicaveis por governanca."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro das timelines territoriais.")
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
    prodes_year_from = int(_ambiente("TITAN_VALIDACAO_PRODES_YEAR_FROM", "2020"))
    prodes_year_to = int(_ambiente("TITAN_VALIDACAO_PRODES_YEAR_TO", "2021"))
    deter_year_from = int(_ambiente("TITAN_VALIDACAO_DETER_YEAR_FROM", str(datetime.now(UTC).year)))
    deter_year_to = int(_ambiente("TITAN_VALIDACAO_DETER_YEAR_TO", str(datetime.now(UTC).year)))

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
    print(f"  PRODES       : {prodes_year_from}..{prodes_year_to}")
    print(f"  DETER        : {deter_year_from}..{deter_year_to}")
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
        prodes_year_from=prodes_year_from,
        prodes_year_to=prodes_year_to,
        deter_year_from=deter_year_from,
        deter_year_to=deter_year_to,
    ).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(
            f"{AMARELO}O script confere forma e status; qualquer decisao comercial que use "
            f"PRODES ou DETER ainda depende de adocao normativa explicita.{FIM}"
        )
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
