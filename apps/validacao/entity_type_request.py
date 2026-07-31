"""Roteiro executavel do pedido de tipo de entidade (EntityTypeRequest).

Cria sua propria Organization e seu proprio admin a cada execucao — nao
depende de semeadura previa nem de identidade ja provisionada, porque o que
este roteiro prova depende justamente de ninguem ja ter vinculo nenhum.

python -m uv run --locked python -m apps.validacao.entity_type_request
python -m uv run --locked python -m apps.validacao.entity_type_request --pausar
"""

import argparse
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine

from apps.bootstrap_admin.__main__ import BootstrapAdminSettings, apply_admin_bootstrap
from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.shared_kernel import OrganizationId


def _montar_roteiro(pretendente: Cliente, admin: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Pedido de tipo de entidade (EntityTypeRequest)", diario=admin.diario)

    roteiro.passo(
        "1",
        "Quem nunca teve vínculo pede para ser PRODUTOR",
        lambda: pretendente.post(
            "/v1/livestock/entity-type-requests",
            {"organization_id": pretendente.organization_id, "requested_kind": "PRODUTOR"},
        ),
        201,
        conferir=lambda r: (
            None if r["status"] == "PENDENTE" and r["decided_at"] is None else "não veio PENDENTE"
        ),
        guardar=lambda r: ids.update(request_id=str(r["request_id"])),
        porque=(
            "O cadastro no Keycloak não concede nada por si só (ADR-0031); isto aqui "
            "é só um pedido, e a API cria o User no primeiro contato autenticado."
        ),
    )
    roteiro.passo(
        "2",
        "Um segundo pedido da mesma pessoa é recusado",
        lambda: pretendente.post(
            "/v1/livestock/entity-type-requests",
            {"organization_id": pretendente.organization_id, "requested_kind": "AUDITOR"},
        ),
        409,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PEDIDO_PENDENTE_JA_EXISTE"
            else "não recusou por pedido pendente duplicado"
        ),
        porque="Sem isso, a mesma pessoa acumularia pedidos concorrentes na fila.",
    )
    roteiro.passo(
        "3",
        "Quem pediu ainda não pode nem listar a própria fila",
        lambda: pretendente.get("/v1/livestock/entity-type-requests"),
        403,
        conferir=lambda r: (
            None
            if r["reason_code"] == "CONTEXTO_ORGANIZACIONAL_NEGADO"
            else "não negou por falta de vínculo"
        ),
        porque="Ter enviado o pedido não é ter Membership — ainda não existe vínculo algum.",
    )
    roteiro.passo(
        "3.1",
        "Quem pediu já consegue ver o próprio status, sem permissão nenhuma",
        lambda: pretendente.get("/v1/livestock/entity-type-requests/mine"),
        200,
        conferir=lambda r: (
            None
            if r["has_membership"] is False and r["requests"][0]["status"] == "PENDENTE"
            else "mine não trouxe pendente sem vínculo"
        ),
        porque=(
            "A autoconsulta é o que a tela de espera do frontend vai chamar — nunca "
            "exige permissão de admin."
        ),
    )
    roteiro.passo(
        "4",
        "O admin vê o pedido na fila de pendentes",
        lambda: admin.get("/v1/livestock/entity-type-requests"),
        200,
        conferir=lambda r: (
            None
            if any(item["request_id"] == ids["request_id"] for item in r.corpo)
            else "o pedido não apareceu na fila do admin"
        ),
        porque="ENTITY_TYPE_REQUEST_LER é a única permissão que abre esta fila.",
    )
    roteiro.passo(
        "5",
        "O admin aprova o pedido",
        lambda: admin.post(f"/v1/livestock/entity-type-requests/{ids['request_id']}/approve"),
        200,
        conferir=lambda r: None if r["status"] == "APROVADA" else "não veio APROVADA",
        porque=(
            "Este é o único ato do sistema que transforma intenção declarada em "
            "Membership e Role reais — na mesma transação da decisão."
        ),
    )
    roteiro.passo(
        "6",
        "Aprovar de novo o mesmo pedido é recusado",
        lambda: admin.post(f"/v1/livestock/entity-type-requests/{ids['request_id']}/approve"),
        409,
        conferir=lambda r: (
            None if r["reason_code"] == "PEDIDO_JA_DECIDIDO" else "não recusou por já decidido"
        ),
    )
    roteiro.passo(
        "7",
        "A prova real: quem pediu agora tem vínculo — mas não é admin",
        lambda: pretendente.get("/v1/livestock/entity-type-requests"),
        403,
        conferir=lambda r: (
            None if r["reason_code"] == "PERMISSAO_AUSENTE" else "não veio PERMISSAO_AUSENTE"
        ),
        porque=(
            "Trocou de motivo: 403 antes era 'você não existe aqui' "
            "(CONTEXTO_ORGANIZACIONAL_NEGADO); agora é 'você existe, só não tem esta "
            "permissão' (PERMISSAO_AUSENTE) — PRODUTOR vira OPERADOR_PECUARIO, que não "
            "administra pedidos de outras pessoas."
        ),
    )
    roteiro.passo(
        "7.1",
        "A autoconsulta agora mostra o vínculo real",
        lambda: pretendente.get("/v1/livestock/entity-type-requests/mine"),
        200,
        conferir=lambda r: (
            None
            if r["has_membership"] is True and r["requests"][0]["status"] == "APROVADA"
            else "mine não trouxe has_membership=true e APROVADA"
        ),
        porque=(
            "É o mesmo endpoint do passo 3.1 — o frontend usa isto para trocar a tela "
            "de espera pelo dashboard."
        ),
    )
    return roteiro


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro do pedido de tipo de entidade.")
    argumentos.add_argument("--pausar", action="store_true")
    opcoes = argumentos.parse_args()

    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    database_url = _ambiente("TITAN_DATABASE_URL", "")
    operadora = _ambiente("TITAN_OPERATOR_ORGANIZATION_ID", "")
    if not database_url or not operadora:
        raise SystemExit(
            "Defina TITAN_DATABASE_URL e TITAN_OPERATOR_ORGANIZATION_ID — este roteiro "
            "cria sua própria Organization e seu próprio admin, e precisa saber onde "
            "gravar o vínculo de identidade."
        )

    organizacao_nova = str(uuid4())
    admin_kc = AdminKeycloak.autenticar(
        base_url=keycloak_url,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin_kc.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)

    sufixo = uuid4().hex[:8]
    usuario_pretendente = f"validacao-pretendente-{sufixo}"
    usuario_admin = f"validacao-admin-{sufixo}"
    admin_kc.garantir_usuario(username=usuario_pretendente, senha=SENHA_DEMONSTRACAO)
    subject_admin = admin_kc.garantir_usuario(username=usuario_admin, senha=SENHA_DEMONSTRACAO)

    engine = create_engine(database_url)
    try:
        resultado_bootstrap = apply_admin_bootstrap(
            engine,
            BootstrapAdminSettings(
                operator_organization_id=OrganizationId.parse(operadora),
                target_organization_id=OrganizationId.parse(organizacao_nova),
                issuer=f"{keycloak_url}/realms/{realm}",
                subject=subject_admin,
                authority_actor_id=uuid4(),
            ),
        )
    finally:
        engine.dispose()

    diario: list[Requisicao] = []
    pretendente = Cliente(
        base_url=api,
        token=admin_kc.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO, username=usuario_pretendente, senha=SENHA_DEMONSTRACAO
        ),
        organization_id=organizacao_nova,
        rotulo="pretendente",
        diario=diario,
    )
    admin = Cliente(
        base_url=api,
        token=admin_kc.token_de_usuario(
            client_id=CLIENTE_DE_VALIDACAO, username=usuario_admin, senha=SENHA_DEMONSTRACAO
        ),
        organization_id=organizacao_nova,
        rotulo="admin",
        diario=diario,
    )

    print(f"{NEGRITO}Ambiente{FIM}")
    print(f"  API              : {api}")
    print(f"  Keycloak         : {keycloak_url} (realm {realm})")
    print(f"  Organization nova: {organizacao_nova}")
    print(
        f"  Admin bootstrado : {resultado_bootstrap['user_id']} "
        f"(Role {resultado_bootstrap['role_id']})"
    )
    print(
        f"{CINZA}  Organization e identidades criadas só para esta execução — nada "
        f"reaproveitado da semeadura de demonstração.{FIM}"
    )
    print(f"  Instante         : {datetime.now(UTC).isoformat()}")

    codigo = _montar_roteiro(pretendente, admin).executar(pausar=opcoes.pausar)
    if codigo == 0:
        print(f"{AMARELO}O script confere forma e status; a leitura de negócio segue humana.{FIM}")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
