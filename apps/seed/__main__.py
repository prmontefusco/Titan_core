"""Semeadura do cenário de demonstração (Passo 10.6, antecipado ao 10.4a).

Monta, num ambiente **local e descartável**, tudo o que a validação manual do
Passo 10.4 exige: duas Organizations, dois papéis com permissões distintas, dois
usuários no Keycloak e os vínculos que ligam um ao outro. Ao final imprime o
roteiro pronto para o Swagger.

Existe porque o portão do 10.4a pede prova na prática, e sem isto qualquer token
válido resulta — corretamente — em `403 CONTEXTO_ORGANIZACIONAL_NEGADO`: o
principal existe e não tem vínculo algum.

**Dados fictícios, ambiente local.** Nada aqui é pessoa real. As senhas são
conhecidas e fixas, o que é aceitável num ambiente descartável e inaceitável em
qualquer outro — por isso a execução exige confirmação explícita.
"""

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Connection, text

from apps.seed.keycloak import AdminKeycloak, KeycloakError
from packages.core_domain import (
    Membership,
    MembershipRoleAssignment,
    Organization,
    Permission,
    Role,
    User,
)
from packages.core_domain.organization_context import ExternalIdentity
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.database import (
    DatabaseSettings,
    create_database_engine,
)
from packages.core_infrastructure.persistence.external_identities import (
    ExternalIdentityRepository,
)
from packages.livestock_application.authorization import (
    ANIMAL_CRIAR,
    AUDITOR,
    DOSSIER_LER,
    ELIGIBILITY_EXECUTAR,
    MEDICATION_CRIAR,
    OPERADOR_PECUARIO,
    ROLE_PERMISSIONS,
    TIMELINE_LER,
    TREATMENT_REGISTRAR,
)
from packages.shared_kernel import OrganizationId, TypedId

TODAS_AS_PERMISSOES = (
    ANIMAL_CRIAR,
    MEDICATION_CRIAR,
    TREATMENT_REGISTRAR,
    ELIGIBILITY_EXECUTAR,
    TIMELINE_LER,
    DOSSIER_LER,
)

SENHA_DEMONSTRACAO = "titan_demo_local"  # noqa: S105 — ambiente local descartável


@dataclass(frozen=True, slots=True)
class Semeado:
    operadora: OrganizationId
    org_a: OrganizationId
    org_b: OrganizationId
    property_id: TypedId
    operador_username: str
    auditor_username: str


def _ambiente(nome: str, padrao: str | None = None) -> str:
    valor = os.environ.get(nome, padrao or "")
    if not valor:
        raise SystemExit(f"Defina {nome} antes de semear.")
    return valor


def _permissoes(connection: Connection, operadora: OrganizationId) -> dict[str, TypedId]:
    """Cria o que falta e reusa o que existe: `permissions.code` é único global."""
    autorizacao = AuthorizationRepository(connection)
    resultado: dict[str, TypedId] = {}
    for codigo in TODAS_AS_PERMISSOES:
        existente = connection.execute(
            text("SELECT permission_id FROM core_identity.permissions WHERE code = :c"),
            {"c": codigo},
        ).scalar_one_or_none()
        if existente is not None:
            resultado[codigo] = TypedId("permission", existente)
            continue
        permissao = Permission.create(operator_organization_id=operadora, code=codigo)
        autorizacao.add_permission(permissao)
        resultado[codigo] = permissao.permission_id
    return resultado


def _identidade_externa(
    connection: Connection,
    *,
    operadora: OrganizationId,
    issuer: str,
    subject: str,
    agora: datetime,
) -> TypedId:
    """Devolve o `user_id` interno, reusando o vínculo externo quando já existe.

    O par (emissor, subject) é único: criar outro faria a resolução do principal
    encontrar duas linhas e falhar.
    """
    set_local_organization_context(connection, operadora)
    existente = connection.execute(
        text(
            "SELECT internal_principal_id FROM core_identity.external_identities "
            "WHERE issuer = :i AND subject = :s"
        ),
        {"i": issuer, "s": subject},
    ).scalar_one_or_none()
    if existente is not None:
        return TypedId("user", existente)

    usuario = User.create(platform_operator_organization_id=operadora)
    UserRepository(connection).add(usuario)
    ExternalIdentityRepository(connection).add(
        ExternalIdentity.link_user(
            operator_organization_id=operadora,
            issuer=issuer,
            subject=subject,
            user_id=usuario.user_id,
            linked_at=agora,
            linked_by_actor_id=TypedId.new("actor"),
        )
    )
    return usuario.user_id


def _vincular(
    connection: Connection,
    *,
    user_id: TypedId,
    organizacao: OrganizationId,
    nome_papel: str,
    permissoes: tuple[TypedId, ...],
    agora: datetime,
) -> None:
    set_local_organization_context(connection, organizacao)
    vinculo = Membership.create(
        user_id=user_id,
        organization_id=organizacao,
        valid_from=agora - timedelta(days=1),
        valid_until=None,
        origin_reference=TypedId.new("membership_invitation"),
        granted_by_actor_id=TypedId.new("actor"),
    )
    MembershipRepository(connection).add(vinculo)

    autorizacao = AuthorizationRepository(connection)
    papel = Role.create(organization_id=organizacao, name=nome_papel, permission_ids=permissoes)
    autorizacao.add_role(papel)
    autorizacao.assign_role(
        MembershipRoleAssignment.create(
            membership_id=vinculo.membership_id,
            role_id=papel.role_id,
            organization_id=organizacao,
            valid_from=agora - timedelta(hours=1),
            valid_until=None,
            granted_by_actor_id=TypedId.new("actor"),
        )
    )


def semear(connection: Connection, *, issuer: str, subs: dict[str, str]) -> Semeado:
    agora = datetime.now(UTC)

    operadora_raw = os.environ.get("TITAN_OPERATOR_ORGANIZATION_ID", "")
    operadora = OrganizationId.parse(operadora_raw) if operadora_raw else OrganizationId.new()
    organizacoes = {"operadora": operadora, "a": OrganizationId.new(), "b": OrganizationId.new()}
    for identificador in organizacoes.values():
        set_local_organization_context(connection, identificador)
        existe = connection.execute(
            text("SELECT 1 FROM core_identity.organizations WHERE organization_id = :o"),
            {"o": identificador.value},
        ).scalar_one_or_none()
        if existe is None:
            OrganizationRepository(connection).add(Organization(organization_id=identificador))

    permissoes = _permissoes(connection, operadora)
    sufixo = uuid4().hex[:8]

    operador_user = _identidade_externa(
        connection,
        operadora=operadora,
        issuer=issuer,
        subject=subs["operador"],
        agora=agora,
    )
    _vincular(
        connection,
        user_id=operador_user,
        organizacao=organizacoes["a"],
        nome_papel=f"{OPERADOR_PECUARIO}_{sufixo}",
        permissoes=tuple(permissoes[c] for c in sorted(ROLE_PERMISSIONS[OPERADOR_PECUARIO])),
        agora=agora,
    )

    auditor_user = _identidade_externa(
        connection,
        operadora=operadora,
        issuer=issuer,
        subject=subs["auditor"],
        agora=agora,
    )
    _vincular(
        connection,
        user_id=auditor_user,
        organizacao=organizacoes["a"],
        nome_papel=f"{AUDITOR}_{sufixo}",
        permissoes=tuple(permissoes[c] for c in sorted(ROLE_PERMISSIONS[AUDITOR])),
        agora=agora,
    )

    # Uma propriedade na Org A: o animal precisa nascer em algum lugar.
    property_id = TypedId.new("rural_property")
    set_local_organization_context(connection, organizacoes["a"])
    connection.execute(
        text(
            "INSERT INTO core_audit.rural_properties ("
            "property_id, record_owner_organization_id, code, name, "
            "municipality, state_code, created_at) "
            "VALUES (:id, :org, :code, 'Fazenda Demonstracao', 'Uberaba', 'MG', NOW())"
        ),
        {
            "id": property_id.value,
            "org": organizacoes["a"].value,
            "code": f"FAZ-DEMO-{sufixo}",
        },
    )

    return Semeado(
        operadora=operadora,
        org_a=organizacoes["a"],
        org_b=organizacoes["b"],
        property_id=property_id,
        operador_username="titan_operador",
        auditor_username="titan_auditor",
    )


def _roteiro(semeado: Semeado, keycloak_url: str) -> str:
    return f"""
================== CENÁRIO SEMEADO ==================

Organização A (com vínculo) : {semeado.org_a.value}
Organização B (sem vínculo) : {semeado.org_b.value}
Organização operadora       : {semeado.operadora.value}
Propriedade na Org A        : {semeado.property_id.value}

Usuários no Keycloak ({keycloak_url}):
  {semeado.operador_username} / {SENHA_DEMONSTRACAO}   -> OPERADOR_PECUARIO
  {semeado.auditor_username} / {SENHA_DEMONSTRACAO}    -> AUDITOR (somente leitura)

--------------- ROTEIRO DE VALIDAÇÃO ----------------

Antes de subir a API, exporte:
  $env:TITAN_OPERATOR_ORGANIZATION_ID = "{semeado.operadora.value}"

No Swagger (http://localhost:8000/docs), use "Authorize" para entrar como cada
usuário. O cabeçalho X-Titan-Organization-Id é campo do próprio formulário.

  1) operador + Org A, corpo válido .................... espera 201
  2) sem Authorize ..................................... espera 401 NAO_AUTENTICADO
  3) auditor + Org A ................................... espera 403 PERMISSAO_AUSENTE
  4) operador + Org B .................................. espera 403 CONTEXTO_ORGANIZACIONAL_NEGADO
  5) operador + Org A, sem o cabeçalho de organização ... espera 400 ORGANIZACAO_NAO_INFORMADA
  6) operador + Org A, "sex": "INEXISTENTE" ............ espera 422 ENTRADA_INVALIDA
  7) o mesmo SISBOV duas vezes ......................... espera 409 CONFLITO_DE_DOMINIO

Corpo para os casos 1, 3, 4 e 7:

  {"{"}
    "birth_property_id": "{semeado.property_id.value}",
    "sex": "MALE",
    "breed": "Nelore"
  {"}"}

No caso 7, acrescente ao corpo e repita a chamada duas vezes:
    "initial_identifier_type": "OFFICIAL_SISBOV",
    "initial_identifier_value": "BR12345678"

=====================================================
"""


def main() -> None:
    # O console do Windows usa cp1252 por padrão e engasga com acentuação e
    # setas. Sem isto, a semeadura funciona e falha ao imprimir o roteiro — o
    # pior dos dois mundos, porque o trabalho é feito e o resultado se perde.
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    if os.environ.get("TITAN_SEED_CONFIRM") != "1":
        raise SystemExit(
            "Esta ferramenta cria usuários com senha conhecida e só faz sentido em "
            "ambiente local descartável.\nDefina TITAN_SEED_CONFIRM=1 para confirmar."
        )

    keycloak_url = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    issuer = _ambiente("TITAN_OIDC_ISSUER", f"{keycloak_url}/realms/{realm}").rstrip("/")

    print(f"Keycloak : {keycloak_url} (realm {realm})")
    print(f"Emissor  : {issuer}")
    print(f"Banco    : {os.environ.get('TITAN_DATABASE_URL', '(não definido)')}\n")

    try:
        admin = AdminKeycloak.autenticar(
            base_url=keycloak_url,
            realm=realm,
            usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
            senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
        )
        subs = {
            "operador": admin.garantir_usuario(username="titan_operador", senha=SENHA_DEMONSTRACAO),
            "auditor": admin.garantir_usuario(username="titan_auditor", senha=SENHA_DEMONSTRACAO),
        }
    except KeycloakError as erro:
        print(f"Falha no Keycloak: {erro}", file=sys.stderr)
        raise SystemExit(1) from erro

    engine = create_database_engine(DatabaseSettings.from_environment())
    try:
        with engine.connect() as connection, connection.begin():
            semeado = semear(connection, issuer=issuer, subs=subs)
    finally:
        engine.dispose()

    print(_roteiro(semeado, keycloak_url))


if __name__ == "__main__":
    main()
