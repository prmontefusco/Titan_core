"""Ambiente HTTP para os testes de API da vertical (Passos 10.4a e 10.4b).

A travessia que este arquivo exercita, do socket ao banco:

    HTTP → OIDC → AuthenticatedPrincipal → OrganizationContext → Permission
         → Application Service → transação → contexto RLS → repositório → PostgreSQL

A autenticação é substituída por um principal fixo, e **só ela**: contexto
organizacional, permissão, transação e RLS são os reais. Substituir a validação
do token não enfraquece a prova — o que se quer provar é o que vem depois dela.

Vive fora de um `conftest.py` porque a classe é importada por mais de um módulo
de teste, e a fixture que a instancia é que fica no conftest.
"""

import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text

from apps.api.authentication import require_authenticated_principal
from apps.api.main import app
from packages.core_application.rule_governance_authorization import (
    RULE_GOVERNANCE_CRIAR,
    RULE_GOVERNANCE_LER,
    RULE_GOVERNANCE_PERMISSIONS,
    RULE_GOVERNANCE_PUBLICAR,
)
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
from packages.livestock_application.authorization import (
    AUDITOR,
    LIVESTOCK_PERMISSIONS,
    OPERADOR_PECUARIO,
    ROLE_PERMISSIONS,
)
from packages.shared_kernel import TypedId

DATABASE_URL = os.environ.get("TITAN_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TITAN_DATABASE_URL não configurada para teste PostgreSQL."
)

ISSUER = "http://localhost:8080/realms/titan"
TODAS_AS_PERMISSOES = LIVESTOCK_PERMISSIONS | RULE_GOVERNANCE_PERMISSIONS
PERMISSOES_OPERADOR = ROLE_PERMISSIONS[OPERADOR_PECUARIO] | frozenset(
    {RULE_GOVERNANCE_CRIAR, RULE_GOVERNANCE_LER, RULE_GOVERNANCE_PUBLICAR}
)
PERMISSOES_AUDITOR = ROLE_PERMISSIONS[AUDITOR] | frozenset({RULE_GOVERNANCE_LER})


class Ambiente:
    """Duas organizações, dois papéis e uma propriedade para o animal nascer.

    Os papéis recebem exatamente os conjuntos declarados em `ROLE_PERMISSIONS`,
    e não um subconjunto conveniente ao teste: um ambiente que conceda menos do
    que a produção concede prova menos do que aparenta.
    """

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
        for codigo in sorted(TODAS_AS_PERMISSOES):
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
            nome_papel=f"{OPERADOR_PECUARIO}_{uuid4().hex[:8]}",
            permissoes=tuple(sorted(PERMISSOES_OPERADOR)),
            agora=agora,
        )
        self.auditor = self._principal_com_papel(
            subject=self.auditor_subject,
            organizacao=self.org_a,
            nome_papel=f"{AUDITOR}_{uuid4().hex[:8]}",
            permissoes=tuple(sorted(PERMISSOES_AUDITOR)),
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


class ClienteAutenticado:
    """Cliente HTTP que carrega o próprio principal.

    O override de autenticação é global à aplicação. Um cliente que o definisse
    apenas na construção seria sobrescrito pelo cliente seguinte, e dois papéis
    no mesmo teste passariam a agir como um só — falha silenciosa que faz o teste
    provar o contrário do que afirma. Aqui o principal é reafirmado a cada
    requisição.
    """

    def __init__(self, principal: AuthenticatedPrincipal | None) -> None:
        self._principal = principal
        self._cliente = TestClient(app, raise_server_exceptions=False)

    def _armar(self) -> None:
        if self._principal is None:
            app.dependency_overrides.pop(require_authenticated_principal, None)
        else:
            principal = self._principal
            app.dependency_overrides[require_authenticated_principal] = lambda: principal

    def post(self, *args: Any, **kwargs: Any) -> Any:
        self._armar()
        return self._cliente.post(*args, **kwargs)

    def get(self, *args: Any, **kwargs: Any) -> Any:
        self._armar()
        return self._cliente.get(*args, **kwargs)


def _cliente(ambiente: Ambiente, principal: AuthenticatedPrincipal | None) -> ClienteAutenticado:
    """Substitui apenas a autenticação; o resto da pilha é o real.

    Sem principal, a dependência real volta a valer — e é ela que responde 401 na
    ausência de token, que é justamente o que o teste quer observar.
    """
    return ClienteAutenticado(principal)
