"""Prova ponta a ponta da fundação HTTP da vertical (Passo 10.4a).

A travessia que este arquivo exercita, do socket ao banco:

    HTTP → OIDC → AuthenticatedPrincipal → OrganizationContext → Permission
         → Application Service → transação → contexto RLS → repositório → PostgreSQL

O endpoint-prova é `POST /v1/livestock/animals`, simples o bastante para não
misturar motor de regras, avaliação, decisão e dossiê na prova do encanamento.

A autenticação é substituída por um principal fixo, e **só ela**: contexto
organizacional, permissão, transação e RLS são os reais. Substituir a validação
do token não enfraquece a prova — o que se quer provar aqui é o que vem depois
dela.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, create_engine, text

from apps.api.authentication import require_authenticated_principal
from apps.api.livestock_dependencies import (
    ORGANIZATION_HEADER,
    operator_organization_id,
    request_connection,
)
from apps.api.main import app
from packages.core_domain import (
    Membership,
    MembershipRoleAssignment,
    Organization,
    Permission,
    Role,
    User,
)
from packages.core_domain.authentication import AuthenticatedPrincipal, PrincipalType
from packages.core_domain.organization_context import ExternalIdentity
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.external_identities import (
    ExternalIdentityRepository,
)
from packages.livestock_application.authorization import ANIMAL_CRIAR, TIMELINE_LER
from packages.shared_kernel import TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)

ISSUER = "http://localhost:8080/realms/titan"


class Ambiente:
    """Duas organizações, dois papéis, e uma propriedade para o animal nascer."""

    def __init__(self, connection: Connection) -> None:
        agora = datetime.now(UTC)
        self.connection = connection

        self.operadora = Organization.create()
        self.org_a = Organization.create()
        self.org_b = Organization.create()
        for organizacao in (self.operadora, self.org_a, self.org_b):
            set_local_organization_context(connection, organizacao.organization_id)
            OrganizationRepository(connection).add(organizacao)

        # `permissions.code` é único global, e a semeadura de demonstração grava
        # esses mesmos códigos. Criar cegamente faria o teste passar só em banco
        # virgem — e falhar em qualquer ambiente já semeado.
        autorizacao = AuthorizationRepository(connection)
        self.permissoes: dict[str, TypedId] = {}
        for codigo in (ANIMAL_CRIAR, TIMELINE_LER):
            existente = connection.execute(
                text("SELECT permission_id FROM core_identity.permissions WHERE code = :c"),
                {"c": codigo},
            ).scalar_one_or_none()
            if existente is not None:
                self.permissoes[codigo] = TypedId("permission", existente)
                continue
            permissao = Permission.create(
                operator_organization_id=self.operadora.organization_id, code=codigo
            )
            autorizacao.add_permission(permissao)
            self.permissoes[codigo] = permissao.permission_id

        # Um usuário operador e um auditor, cada um com o papel que lhe cabe.
        self.operador_subject = f"operador-{uuid4().hex}"
        self.auditor_subject = f"auditor-{uuid4().hex}"
        self.operador = self._principal_com_papel(
            subject=self.operador_subject,
            organizacao=self.org_a,
            nome_papel=f"OPERADOR_PECUARIO_{uuid4().hex[:8]}",
            permissoes=(ANIMAL_CRIAR,),
            agora=agora,
        )
        self.auditor = self._principal_com_papel(
            subject=self.auditor_subject,
            organizacao=self.org_a,
            nome_papel=f"AUDITOR_{uuid4().hex[:8]}",
            permissoes=(TIMELINE_LER,),
            agora=agora,
        )

        self.property_id = TypedId.new("rural_property")
        set_local_organization_context(connection, self.org_a.organization_id)
        connection.execute(
            text(
                "INSERT INTO core_audit.rural_properties ("
                "property_id, record_owner_organization_id, code, name, "
                "municipality, state_code, created_at) "
                "VALUES (:id, :org, 'FAZ-1', 'Fazenda', 'Uberaba', 'MG', NOW())"
            ),
            {"id": self.property_id.value, "org": self.org_a.organization_id.value},
        )

    def _principal_com_papel(
        self,
        *,
        subject: str,
        organizacao: Organization,
        nome_papel: str,
        permissoes: tuple[str, ...],
        agora: datetime,
    ) -> AuthenticatedPrincipal:
        set_local_organization_context(self.connection, self.operadora.organization_id)
        usuario = User.create(platform_operator_organization_id=self.operadora.organization_id)
        UserRepository(self.connection).add(usuario)
        ExternalIdentityRepository(self.connection).add(
            ExternalIdentity.link_user(
                operator_organization_id=self.operadora.organization_id,
                issuer=ISSUER,
                subject=subject,
                user_id=usuario.user_id,
                linked_at=agora,
                linked_by_actor_id=TypedId.new("actor"),
            )
        )

        set_local_organization_context(self.connection, organizacao.organization_id)
        vinculo = Membership.create(
            user_id=usuario.user_id,
            organization_id=organizacao.organization_id,
            valid_from=agora - timedelta(days=1),
            valid_until=None,
            origin_reference=TypedId.new("membership_invitation"),
            granted_by_actor_id=TypedId.new("actor"),
        )
        MembershipRepository(self.connection).add(vinculo)

        autorizacao = AuthorizationRepository(self.connection)
        papel = Role.create(
            organization_id=organizacao.organization_id,
            name=nome_papel,
            permission_ids=tuple(self.permissoes[c] for c in permissoes),
        )
        autorizacao.add_role(papel)
        autorizacao.assign_role(
            MembershipRoleAssignment.create(
                membership_id=vinculo.membership_id,
                role_id=papel.role_id,
                organization_id=organizacao.organization_id,
                valid_from=agora - timedelta(hours=1),
                valid_until=None,
                granted_by_actor_id=TypedId.new("actor"),
            )
        )

        return AuthenticatedPrincipal(
            issuer=ISSUER,
            subject=subject,
            principal_type=PrincipalType.USER,
            authenticated_at=agora,
            client_id="titan-swagger",
            technical_scopes=frozenset({"openid"}),
        )


@pytest.fixture
def ambiente() -> Iterator[Ambiente]:
    """Um ambiente por teste, desfeito ao final: nada vaza para o teste seguinte."""
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        montado = Ambiente(connection)

        # A API reusa esta mesma conexão e transação, para que o que ela grava
        # seja desfeito junto com o cenário.
        # O usuário `titan` é superusuário e IGNORA RLS. Sob ele, o isolamento
        # entre organizações não é exercido de verdade — a consulta de vínculos
        # enxergaria o vínculo de outra organização e o contexto seria concedido.
        # As requisições da API rodam sob um role sem BYPASSRLS, que é o único
        # jeito de a prova valer.
        role = f"titan_api_{uuid4().hex[:12]}"
        connection.execute(
            text(
                f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB '
                "NOCREATEROLE NOINHERIT NOBYPASSRLS"
            )
        )
        for schema in ("core_identity", "core_audit"):
            connection.execute(text(f'GRANT USAGE ON SCHEMA {schema} TO "{role}"'))
            connection.execute(
                text(f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {schema} TO "{role}"')
            )

        originais = dict(app.dependency_overrides)

        def conexao_sob_role_restrito() -> Iterator[Connection]:
            connection.execute(text(f'SET LOCAL ROLE "{role}"'))
            try:
                yield connection
            finally:
                connection.execute(text("RESET ROLE"))

        app.dependency_overrides[request_connection] = conexao_sob_role_restrito
        os.environ["TITAN_OPERATOR_ORGANIZATION_ID"] = str(montado.operadora.organization_id.value)
        operator_organization_id.cache_clear()
        try:
            yield montado
        finally:
            # Restaura em vez de limpar: o `main` registra aqui a autenticação
            # real, e apagá-la deixaria a aplicação sem autenticação para os
            # testes seguintes.
            app.dependency_overrides.clear()
            app.dependency_overrides.update(originais)
            operator_organization_id.cache_clear()
            connection.execute(text("RESET ROLE"))
            transaction.rollback()


def _cliente(ambiente: Ambiente, principal: AuthenticatedPrincipal | None) -> TestClient:
    """Substitui apenas a autenticação; o resto da pilha é o real.

    Sem principal, a dependência real volta a valer — e é ela que responde 401 na
    ausência de token, que é justamente o que o teste quer observar.
    """
    if principal is None:
        app.dependency_overrides.pop(require_authenticated_principal, None)
    else:
        app.dependency_overrides[require_authenticated_principal] = lambda: principal
    return TestClient(app, raise_server_exceptions=False)


def _corpo(ambiente: Ambiente) -> dict[str, object]:
    return {
        "birth_property_id": str(ambiente.property_id.value),
        "sex": "MALE",
        "breed": "Nelore",
    }


def test_operador_autorizado_cria_o_animal(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["organization_id"] == str(ambiente.org_a.organization_id.value)
    assert corpo["animal_id"]


def test_sem_token_a_resposta_e_401(ambiente: Ambiente) -> None:
    """401 diz 'não sei quem você é' — e precisa dizer isso no corpo.

    Um `reason_code` genérico obrigaria o cliente a adivinhar se falta credencial
    ou se houve outra falha qualquer. Foi o que a validação manual encontrou: o
    handler genérico devolvia `ERRO_HTTP`.
    """
    cliente = _cliente(ambiente, None)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 401
    corpo = resposta.json()
    assert corpo["reason_code"] == "NAO_AUTENTICADO"
    # Mensagem própria e em português: o esquema OAuth2 do FastAPI responde antes
    # da nossa dependência, e o texto dele destoaria do resto da API.
    assert corpo["detail"] == "Access Token ausente, inválido ou expirado."
    assert resposta.headers["www-authenticate"] == "Bearer"
    assert resposta.headers["content-type"].startswith("application/problem+json")


def test_sem_a_permissao_exigida_a_resposta_e_403(ambiente: Ambiente) -> None:
    """403 diz 'sei quem você é, e você não pode' — o auditor não escreve."""
    cliente = _cliente(ambiente, ambiente.auditor)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "PERMISSAO_AUSENTE"
    assert resposta.headers["content-type"].startswith("application/problem+json")


def test_organizacao_sem_vinculo_e_negada(ambiente: Ambiente) -> None:
    """O operador da Org A não opera na Org B, e a negação não revela o porquê."""
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_b.organization_id.value)},
    )

    assert resposta.status_code == 403
    assert resposta.json()["reason_code"] == "CONTEXTO_ORGANIZACIONAL_NEGADO"


def test_cabecalho_de_organizacao_ausente_e_recusado(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post("/v1/livestock/animals", json=_corpo(ambiente))

    assert resposta.status_code == 400
    assert resposta.json()["reason_code"] == "ORGANIZACAO_NAO_INFORMADA"


def test_entrada_invalida_devolve_422_em_problem_json(ambiente: Ambiente) -> None:
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json={"birth_property_id": str(ambiente.property_id.value), "sex": "INEXISTENTE"},
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )

    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo["reason_code"] == "ENTRADA_INVALIDA"
    assert corpo["errors"]


def test_conflito_de_dominio_devolve_409(ambiente: Ambiente) -> None:
    """Identificador oficial repetido é recusa do domínio, não erro do servidor."""
    cliente = _cliente(ambiente, ambiente.operador)
    corpo = _corpo(ambiente) | {
        "initial_identifier_type": "OFFICIAL_SISBOV",
        "initial_identifier_value": f"BR{uuid4().hex[:10]}",
    }
    cabecalho = {ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)}

    assert cliente.post("/v1/livestock/animals", json=corpo, headers=cabecalho).status_code == 201
    repetido = cliente.post("/v1/livestock/animals", json=corpo, headers=cabecalho)

    assert repetido.status_code == 409
    assert repetido.json()["reason_code"] == "CONFLITO_DE_DOMINIO"


def test_o_animal_criado_nasce_com_o_evento_no_log_do_core(ambiente: Ambiente) -> None:
    """Registro e prova nascem juntos: a transação cobre os dois."""
    cliente = _cliente(ambiente, ambiente.operador)

    resposta = cliente.post(
        "/v1/livestock/animals",
        json=_corpo(ambiente),
        headers={ORGANIZATION_HEADER: str(ambiente.org_a.organization_id.value)},
    )
    animal_id = resposta.json()["animal_id"]

    eventos = (
        ambiente.connection.execute(
            text(
                "SELECT event_type FROM core_audit.domain_events "
                "WHERE aggregate_id = :id ORDER BY aggregate_version"
            ),
            {"id": animal_id},
        )
        .scalars()
        .all()
    )

    assert eventos == ["livestock.animal_registered"]
