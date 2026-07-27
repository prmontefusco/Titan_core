"""Roteiro executavel da simulacao comercial ponta a ponta ate o frigorifico.

python -m uv run --locked python -m apps.validacao.simulacao_comercial
python -m uv run --locked python -m apps.validacao.simulacao_comercial --pausar
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.matriz_elegibilidade_mercados import _preparar_regras_de_mercado
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.livestock_application.market_eligibility import MarketEligibilityPurpose


def _montar_roteiro(operador: Cliente, auditor: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    agora = datetime.now(UTC)
    transferencia = agora - timedelta(days=1)
    # A carencia importada no passo 4 declara withdrawal_period_days=45; o
    # tratamento precisa ter ocorrido ha mais que isso para que o animal
    # chegue elegivel na matriz do passo 5, como o roteiro pretende
    # demonstrar. Com 30 dias antes da transferencia, o animal ainda estaria
    # dentro da carencia (30 < 45) e a matriz corretamente diria NAO_ELEGIVEL
    # -- resultado real, so nao o que este roteiro quer exercitar.
    tratamento = transferencia - timedelta(days=60)
    roteiro = Roteiro(
        "Simulacao comercial - fazenda, prova recebida, elegibilidade e frigorifico",
        diario=operador.diario,
    )

    roteiro.passo(
        "1",
        "Operador cadastra a fazenda de destino e o animal local",
        lambda: _criar_cenario_local(operador, ids),
        201,
        conferir=lambda r: None if ids.get("animal_id") else "cenario local nao foi criado",
        porque=(
            "A simulacao parte de um animal que ja esta na Organization ativa; "
            "a cadeia externa chega por prova, nao por acesso ao tenant alheio."
        ),
    )
    roteiro.passo(
        "2",
        "Operador cadastra a fazenda de origem como contraparte externa",
        lambda: operador.post(
            "/v1/livestock/external-counterparties",
            {
                "name": "Fazenda Origem Comercial",
                "counterparty_type": "FARM",
                "identifiers": [f"CAR:MT-{uuid4().hex[:12]}"],
                "notes": "Origem ficticia para simulacao comercial.",
            },
        ),
        201,
        conferir=lambda r: None if r["counterparty_id"] else "sem counterparty_id da origem",
        guardar=lambda r: ids.update(source_counterparty_id=str(r["counterparty_id"])),
        porque="A cadeia anterior a Organization vira cadastro local e auditavel.",
    )
    roteiro.passo(
        "3",
        "Operador registra o artefato recebido da origem",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/received-transfer-artifacts",
            {
                "source_counterparty_id": ids["source_counterparty_id"],
                "bundle_digest": "c" * 64,
                "bundle_issued_at": transferencia.isoformat(),
                "transfer_effective_at": transferencia.isoformat(),
                "coverage_known_until": transferencia.isoformat(),
                "issuer_name": "Fazenda Origem Comercial",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["source_counterparty_id"] == ids["source_counterparty_id"]
            else "artefato nao preservou a origem declarada"
        ),
        guardar=lambda r: ids.update(artifact_id=str(r["artifact_id"])),
        porque="A simulacao nao cola identificadores: ela prova de onde veio a historia.",
    )
    roteiro.passo(
        "4",
        "Operador importa o tratamento vindo da fazenda de origem",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/imported-facts",
            {
                "source_artifact_id": ids["artifact_id"],
                "fact_type": "livestock.treatment_applied",
                "occurred_at": tratamento.isoformat(),
                "asserted_by": "Fazenda Origem Comercial",
                "confidence_tier": "CRYPTOGRAPHICALLY_ATTESTED",
                "payload": {"withdrawal_period_days": 45, "substance": "produto ficticio"},
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["origin"] == "IMPORTED_ASSERTION"
            and r["asserted_by"] == "Fazenda Origem Comercial"
            else "fato importado nao preservou autoria externa"
        ),
        guardar=lambda r: ids.update(imported_fact_id=str(r["imported_fact_id"])),
        porque="A prova importada alimenta a decisao sem virar afirmacao do destinatario.",
    )
    roteiro.passo(
        "5",
        "Operador executa a matriz comercial do animal",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/eligibility/market-matrix",
            {},
        ),
        201,
        conferir=lambda r: (
            None
            if _matriz_comercial_tem_forma_esperada(r["markets"])
            else "matriz nao trouxe comparacao comercial esperada"
        ),
        porque=(
            "A comparacao final precisa expor China e EUA lado a lado com motivo, "
            "e a Uniao Europeia como ausencia declarada."
        ),
    )
    roteiro.passo(
        "6",
        "Operador cadastra o frigorifico de destino",
        lambda: operador.post(
            "/v1/livestock/external-counterparties",
            {
                "name": "Frigorifico Destino Validacao",
                "counterparty_type": "SLAUGHTERHOUSE",
                "identifiers": [f"SIF:{uuid4().hex[:8].upper()}"],
                "notes": "Frigorifico ficticio para simulacao comercial.",
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["counterparty_type"] == "SLAUGHTERHOUSE"
            else "contraparte do frigorifico veio com tipo incorreto"
        ),
        guardar=lambda r: ids.update(slaughterhouse_id=str(r["counterparty_id"])),
        porque="O destino comercial precisa ficar nomeado como terceiro especifico.",
    )
    roteiro.passo(
        "7",
        "Operador registra a qualificacao auditavel do frigorifico para a China",
        lambda: operador.post(
            f"/v1/livestock/external-counterparties/{ids['slaughterhouse_id']}/establishment-qualifications",
            {
                "market_purpose": MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                "status": "HABILITADO",
                "source_name": "lista-sif-ficticia",
                "source_version": "2026-07",
                "assessed_at": agora.isoformat(),
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["market_purpose"] == MarketEligibilityPurpose.EXPORTACAO_CHINA.code
            and r["status"] == "HABILITADO"
            else "qualificacao do frigorifico nao foi registrada para a China"
        ),
        porque=(
            "Ter SIF nao basta por si: a habilitacao para o mercado precisa virar "
            "dado auditavel com fonte e versao declaradas."
        ),
    )
    roteiro.passo(
        "8",
        "Operador reexecuta a matriz com o frigorifico escolhido",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/eligibility/market-matrix",
            {"slaughterhouse_counterparty_id": ids["slaughterhouse_id"]},
        ),
        201,
        conferir=lambda r: (
            None
            if _matriz_comercial_com_sujeito_escolhido_tem_forma_esperada(
                r["markets"], ids["slaughterhouse_id"]
            )
            else "matriz nao refletiu o frigorifico escolhido como dependencia resolvida"
        ),
        porque=(
            "Escolher o frigorifico deve promover a China a elegivel quando o "
            "estabelecimento escolhido for um frigorifico com SIF."
        ),
    )
    roteiro.passo(
        "9",
        "Operador registra o abate apontando para o frigorifico",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/exit",
            {
                "exit_type": "ABATE",
                "occurred_at": agora.isoformat(),
                "reason": "Abate comercial validado pelo roteiro.",
                "destination_counterparty_id": ids["slaughterhouse_id"],
            },
        ),
        201,
        conferir=lambda r: (
            None
            if r["exit_type"] == "ABATE"
            and r["destination_counterparty_id"] == ids["slaughterhouse_id"]
            else "saida nao preservou o frigorifico do abate"
        ),
        porque="A simulacao termina no frigorifico sem perder o vinculo comercial do destino.",
    )
    roteiro.passo(
        "10",
        "Operador lista o rebanho historico e reencontra o animal abatido",
        lambda: operador.get("/v1/livestock/animals?incluir_saidos=true&limit=200"),
        200,
        conferir=lambda r: (
            None
            if _animal_aparece_com_saida_para_frigorifico(
                r["items"], ids["animal_id"], ids["slaughterhouse_id"]
            )
            else "animal abatido nao apareceu com saida para o frigorifico"
        ),
        porque="A UI e a auditoria precisam reencontrar o desfecho comercial sem UUID copiado.",
    )
    roteiro.passo(
        "11",
        "Auditor nao registra nova saida no lugar do operador",
        lambda: auditor.post(
            f"/v1/livestock/animals/{ids['animal_id']}/exit",
            {
                "exit_type": "ABATE",
                "occurred_at": agora.isoformat(),
                "reason": "Nao deveria passar.",
                "destination_counterparty_id": ids["slaughterhouse_id"],
            },
        ),
        403,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PERMISSAO_AUSENTE"
            else "negacao nao informou ausencia de permissao"
        ),
        porque="Ver a cadeia nao concede autoridade para alterar o desfecho dela.",
    )
    return roteiro


def _criar_cenario_local(operador: Cliente, ids: dict[str, str]) -> object:
    propriedade = operador.post(
        "/v1/livestock/properties",
        {
            "code": f"PROP-{uuid4().hex[:8]}",
            "name": "Fazenda Destino Comercial",
            "municipality": "Cuiaba",
            "state_code": "MT",
        },
    )
    if propriedade.status != 201:
        return propriedade
    ids["property_id"] = str(propriedade["property_id"])
    animal = operador.post(
        "/v1/livestock/animals",
        {"birth_property_id": ids["property_id"], "sex": "MALE"},
    )
    if animal.status == 201:
        ids["animal_id"] = str(animal["animal_id"])
    return animal


def _matriz_comercial_tem_forma_esperada(markets: list[dict[str, object]]) -> bool:
    por_mercado = {str(item["market"]): item for item in markets}
    china = MarketEligibilityPurpose.EXPORTACAO_CHINA.code
    estados_unidos = MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code
    europa = MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code
    if set(por_mercado) != {china, estados_unidos, europa}:
        return False
    requisitos_china = por_mercado[china].get("requirements")
    requisitos_eua = por_mercado[estados_unidos].get("requirements")
    lacunas_europa = por_mercado[europa].get("gaps")
    dependencia_china = por_mercado[china].get("dependency")
    lacunas_china = por_mercado[china].get("gaps")
    return (
        por_mercado[china].get("status") == "CONDICIONADO"
        and por_mercado[estados_unidos].get("status") == "ELEGIVEL"
        and por_mercado[europa].get("status") == "AUSENTE"
        and isinstance(requisitos_china, list)
        and len(requisitos_china) == 2
        and requisitos_china[0].get("status") == "ELEGIVEL"
        and requisitos_china[1].get("status") == "CONDICIONADO"
        and isinstance(dependencia_china, dict)
        and dependencia_china.get("subject_key") == "slaughterhouse"
        and dependencia_china.get("selected_subject_id") is None
        and isinstance(lacunas_china, list)
        and bool(lacunas_china)
        and lacunas_china[0].get("code") == "DEPENDENCIA_DE_SUJEITO_NAO_ESCOLHIDO"
        and isinstance(requisitos_eua, list)
        and bool(requisitos_eua)
        and requisitos_eua[0].get("status") == "ELEGIVEL"
        and isinstance(lacunas_europa, list)
        and bool(lacunas_europa)
        and lacunas_europa[0].get("code") == "REGRA_GOVERNADA_AUSENTE"
    )


def _matriz_comercial_com_sujeito_escolhido_tem_forma_esperada(
    markets: list[dict[str, object]], slaughterhouse_id: str
) -> bool:
    por_mercado = {str(item["market"]): item for item in markets}
    china = MarketEligibilityPurpose.EXPORTACAO_CHINA.code
    estados_unidos = MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code
    europa = MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code
    if set(por_mercado) != {china, estados_unidos, europa}:
        return False
    requisitos_china = por_mercado[china].get("requirements")
    dependencia_china = por_mercado[china].get("dependency")
    return (
        por_mercado[china].get("status") == "ELEGIVEL"
        and por_mercado[estados_unidos].get("status") == "ELEGIVEL"
        and por_mercado[europa].get("status") == "AUSENTE"
        and isinstance(dependencia_china, dict)
        and dependencia_china.get("subject_key") == "slaughterhouse"
        and dependencia_china.get("selected_subject_id") == slaughterhouse_id
        and por_mercado[china].get("gaps") == []
        and isinstance(requisitos_china, list)
        and len(requisitos_china) == 2
        and requisitos_china[0].get("status") == "ELEGIVEL"
        and requisitos_china[1].get("status") == "ELEGIVEL"
        and isinstance(requisitos_china[1].get("dependency"), dict)
        and requisitos_china[1]["dependency"].get("selected_subject_id") == slaughterhouse_id
        and requisitos_china[1].get("gaps") == []
    )


def _animal_aparece_com_saida_para_frigorifico(
    items: list[dict[str, object]], animal_id: str, slaughterhouse_id: str
) -> bool:
    for item in items:
        if str(item.get("animal_id")) != animal_id:
            continue
        saida = item.get("saida")
        return (
            isinstance(saida, dict)
            and saida.get("exit_type") == "ABATE"
            and saida.get("destination_counterparty_id") == slaughterhouse_id
        )
    return False


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da simulacao comercial.")
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
        raise SystemExit(
            "Defina TITAN_DATABASE_URL para o roteiro preparar regras e descobrir a Organization."
        )
    organizacao = opcoes.organizacao or _descobrir_organizacao(database_url)
    _preparar_regras_de_mercado(database_url, organizacao)

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
    print(
        "  Mercados     : "
        + ", ".join(
            (
                MarketEligibilityPurpose.EXPORTACAO_CHINA.code,
                MarketEligibilityPurpose.EXPORTACAO_ESTADOS_UNIDOS.code,
                MarketEligibilityPurpose.EXPORTACAO_UNIAO_EUROPEIA.code,
            )
        )
    )
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
