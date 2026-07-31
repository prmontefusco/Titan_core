"""Roteiro executavel do embargo ambiental do IBAMA via HTTP real.

python -m uv run --locked python -m apps.validacao.embargo_ibama
python -m uv run --locked python -m apps.validacao.embargo_ibama --pausar
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
    """Sonda o caminho real antes do primeiro passo de negocio.

    O risco aberto aqui nao e "algum teste pode falhar"; e gastar a rodada toda
    para descobrir no meio do roteiro que o provider nem estava configurado.
    """
    inexistente = "00000000-0000-4000-8000-000000000000"
    resposta = operador.get(f"/v1/livestock/properties/{inexistente}/environmental-embargoes/ibama")
    if resposta.status == 503 and resposta.corpo.get("reason_code") == "PROVIDER_NAO_CONFIGURADO":
        raise SystemExit(
            f"{AMARELO}O provider Titan_geodata nao esta configurado na API atual.{FIM}\n"
            "Defina TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY no ambiente da API,\n"
            "reinicie o servidor e rode este roteiro de novo."
        )


def _montar_roteiro(operador: Cliente, auditor: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Embargo ambiental do IBAMA via HTTP real", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador cria a propriedade da validacao",
        lambda: operador.post(
            "/v1/livestock/properties",
            {
                "code": f"IBAMA-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
                "name": "Fazenda de validacao do embargo IBAMA",
                "municipality": "Dourados",
                "state_code": "MS",
            },
        ),
        201,
        conferir=lambda r: None if r["property_id"] else "sem property_id",
        guardar=lambda r: ids.update(property_id=str(r["property_id"])),
        porque="O roteiro descobre e cria o proprio alvo; nenhum identificador e copiado a mao.",
    )
    roteiro.passo(
        "2",
        "Operador registra a geometria que sera consultada no provider",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/geometry",
            {"source": "DECLARADA", "geojson": QUADRADO_MS},
        ),
        201,
        conferir=lambda r: (
            None
            if r["geometry_id"] and r["source"] == "DECLARADA" and r["version"] >= 1
            else "geometria nao voltou com id, fonte declarada e versao"
        ),
        guardar=lambda r: ids.update(geometry_id=str(r["geometry_id"])),
        porque=(
            "O embargo cruza a geometria vigente contra a camada externa; sem geometria "
            "vigente o endpoint so poderia devolver lacuna."
        ),
    )
    roteiro.passo(
        "3",
        "Operador avalia os embargos do IBAMA em leitura",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/environmental-embargoes/ibama"
        ),
        200,
        conferir=lambda r: (
            None
            if r["property_id"] == ids["property_id"]
            and r["source"] == "IBAMA"
            and r["layer"] == "IBAMA_EMBARGOS"
            and isinstance(r["version_ids"], list)
            and isinstance(r["restrictions"], list)
            and isinstance(r["gaps"], list)
            else "avaliacao nao trouxe a forma esperada do provider e da geometria"
        ),
        porque=(
            "Esta chamada responde o que o provider diz agora, sem ainda congelar o "
            "resultado como fato auditavel."
        ),
    )
    roteiro.passo(
        "4",
        "Operador congela a avaliacao como assertion auditavel",
        lambda: operador.post(
            f"/v1/livestock/properties/{ids['property_id']}/environmental-embargoes/ibama/assertions",
            {},
        ),
        201,
        conferir=lambda r: (
            None
            if r["property_id"] == ids["property_id"]
            and r["source_name"] == "IBAMA"
            and r["source_layer"] == "IBAMA_EMBARGOS"
            and r["geometry_id"] == ids["geometry_id"]
            and isinstance(r["restrictions"], list)
            and r["recorded_at"]
            else "assertion nao preservou fonte, geometria e registro esperados"
        ),
        guardar=lambda r: ids.update(assertion_id=str(r["assertion_id"])),
        porque=(
            "Aqui o Titan deixa de apenas reconsultar e passa a registrar um fato "
            "reproduzivel sobre o que foi observado no instante da consulta."
        ),
    )
    roteiro.passo(
        "5",
        "Operador consulta o historico gravado da propriedade",
        lambda: operador.get(
            f"/v1/livestock/properties/{ids['property_id']}/environmental-embargoes/ibama/assertions"
        ),
        200,
        conferir=lambda r: (
            None
            if r["items"]
            and r["items"][0]["assertion_id"] == ids["assertion_id"]
            and r["items"][0]["geometry_id"] == ids["geometry_id"]
            else "historico nao devolveu a assertion gravada nesta execucao"
        ),
        porque=(
            "A pergunta muda: nao e mais o que o provider responderia agora, e sim o "
            "que o Titan congelou e consegue recontar."
        ),
    )
    roteiro.passo(
        "6",
        "Auditor le o historico, mas nao grava nova assertion",
        lambda: auditor.post(
            f"/v1/livestock/properties/{ids['property_id']}/environmental-embargoes/ibama/assertions",
            {},
        ),
        403,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PERMISSAO_AUSENTE"
            else "negacao nao informou ausencia de permissao"
        ),
        porque="Consultar auditoria nao concede autoridade para congelar novo fato.",
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do embargo ambiental do IBAMA.")
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
    print(
        f"{CINZA}  Este roteiro depende do Titan_geodata configurado na API "
        f"(TITAN_GEODATA_URL e TITAN_GEODATA_API_KEY).{FIM}"
    )

    _exigir_provider_configurado(operador)

    codigo = _montar_roteiro(operador, auditor).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negocio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
