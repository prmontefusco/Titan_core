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
from packages.core_application.policy_authorization import (
    POLICY_CRIAR,
    POLICY_LER,
    POLICY_PERMISSIONS,
    POLICY_PUBLICAR,
)
from packages.core_application.rule_governance_authorization import (
    RULE_GOVERNANCE_ADOTAR,
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
    AUDITOR,
    LIVESTOCK_PERMISSIONS,
    OPERADOR_PECUARIO,
    ROLE_PERMISSIONS,
)
from packages.shared_kernel import OrganizationId, TypedId

# Derivada da fonte única, e não repetida aqui. Uma lista paralela fica para trás
# em silêncio quando uma permissão nova nasce — foi o que aconteceu ao acrescentar
# as permissões de leitura.
TODAS_AS_PERMISSOES = tuple(
    sorted(LIVESTOCK_PERMISSIONS | RULE_GOVERNANCE_PERMISSIONS | POLICY_PERMISSIONS)
)
PERMISSOES_OPERADOR = ROLE_PERMISSIONS[OPERADOR_PECUARIO] | frozenset(
    {
        RULE_GOVERNANCE_ADOTAR,
        RULE_GOVERNANCE_CRIAR,
        RULE_GOVERNANCE_LER,
        RULE_GOVERNANCE_PUBLICAR,
        POLICY_CRIAR,
        POLICY_LER,
        POLICY_PUBLICAR,
    }
)
PERMISSOES_AUDITOR = ROLE_PERMISSIONS[AUDITOR] | frozenset({RULE_GOVERNANCE_LER, POLICY_LER})

SENHA_DEMONSTRACAO = "titan_demo_local"  # noqa: S105 — ambiente local descartável

# O padrão do Keycloak são cinco minutos, e o roteiro de validação manual não
# cabe nisso: o token expira no meio e o 401 resultante parece defeito da API.
DURACAO_DO_TOKEN_SEGUNDOS = 3600


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
        permissoes=tuple(permissoes[c] for c in sorted(PERMISSOES_OPERADOR)),
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
        permissoes=tuple(permissoes[c] for c in sorted(PERMISSOES_AUDITOR)),
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
    # Datas prontas para colar. Placeholder em roteiro é convite a ser enviado
    # literalmente — e a API, corretamente, responde 422 a `<hoje menos 10 dias>`.
    hoje = datetime.now(UTC)
    aplicado_em = (hoje - timedelta(days=10)).strftime("%Y-%m-%dT12:00:00Z")
    corrigido_em = (hoje - timedelta(days=9)).strftime("%Y-%m-%dT12:00:00Z")
    antes_do_tratamento = (hoje - timedelta(days=20)).strftime("%Y-%m-%dT00:00:00Z")
    no_futuro = (hoje + timedelta(days=1)).strftime("%Y-%m-%dT12:00:00Z")
    # A saída divide a linha do tempo em duas metades, e é essa divisão que a
    # Parte 5 põe à prova: o que ocorreu antes dela ainda entra, o que ocorreu
    # depois não pode ter ocorrido.
    saida_em = (hoje - timedelta(days=5)).strftime("%Y-%m-%dT12:00:00Z")
    depois_da_saida = (hoje - timedelta(days=3)).strftime("%Y-%m-%dT12:00:00Z")
    antes_da_saida = (hoje - timedelta(days=7)).strftime("%Y-%m-%dT12:00:00Z")
    validade_do_lote = (hoje + timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    org_a = semeado.org_a.value
    org_b = semeado.org_b.value
    propriedade = semeado.property_id.value
    return f"""
================== CENÁRIO SEMEADO ==================

Organização A (com vínculo) : {org_a}
Organização B (sem vínculo) : {org_b}
Organização operadora       : {semeado.operadora.value}
Propriedade na Org A        : {propriedade}

Usuários no Keycloak ({keycloak_url}):
  {semeado.operador_username} / {SENHA_DEMONSTRACAO}   -> OPERADOR_PECUARIO (escreve)
  {semeado.auditor_username} / {SENHA_DEMONSTRACAO}    -> AUDITOR (somente leitura)


=============== PREPARAR O AMBIENTE ================

1. Suba a API numa janela dedicada, com as quatro variáveis:

   $env:TITAN_DATABASE_URL = "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan"
   $env:TITAN_OPERATOR_ORGANIZATION_ID = "{semeado.operadora.value}"
   $env:TITAN_OIDC_ISSUER = "http://localhost:8080/realms/titan"
   $env:TITAN_OIDC_AUDIENCE = "titan-api"
   python -m uv run --locked uvicorn apps.api.main:app --port 8000

   Espere "Application startup complete".

2. Abra http://localhost:8000/docs — precisa ser localhost e porta 8000, que é
   o endereço que o Keycloak aceita de volta.

3. Clique em "Authorize", marque o escopo openid, e entre como
   {semeado.operador_username}. Confira que o cadeado das rotas fechou.

   O token vale {DURACAO_DO_TOKEN_SEGUNDOS}s neste realm local (o padrão do Keycloak são
   5 minutos, curto demais para o roteiro). Se ainda assim vier 401
   NAO_AUTENTICADO no meio do caminho, é a credencial vencendo: clique em
   "Authorize" de novo e refaça o passo.

Em toda chamada, o campo X-Titan-Organization-Id recebe:  {org_a}


========= PARTE 1 — O FLUXO COMPLETO (operador) ==========

Cada passo devolve um identificador que o passo seguinte usa. Anote-os.

  1.1  POST /v1/livestock/animals ....................... espera 201
       {{
         "birth_property_id": "{propriedade}",
         "sex": "FEMALE",
         "breed": "Nelore"
       }}
       >>> anote  animal_id

  1.2  POST /v1/livestock/medications ................... espera 201
       {{
         "trade_name": "Ivomec Gold",
         "active_ingredient": "Ivermectina",
         "manufacturer": "Boehringer",
         "withdrawal_period_days": 30
       }}
       >>> anote  medication_id

  1.3  POST /v1/livestock/medication-batches ............ espera 201
       {{
         "medication_id": "<medication_id do passo 1.2>",
         "batch_number": "LOTE-2026-001",
         "expiry_date": "{validade_do_lote}"
       }}
       >>> anote  batch_id

  1.4  POST /v1/livestock/treatments .................... espera 201
       A data abaixo é de dez dias atrás, e a carência é de 30 dias: o animal
       tem de ficar bloqueado.
       {{
         "animal_id": "<animal_id>",
         "medication_batch_id": "<batch_id>",
         "applied_at": "{aplicado_em}",
         "dose": "1 mL / 50 kg",
         "evidence_notes": ["foto no celular do Joao"]
       }}
       >>> anote  application_id

  1.5  POST /v1/livestock/animals/<animal_id>/eligibility ... espera 201
       Sem corpo.
       >>> CONFIRA:  "result": "rejeitada"
       >>> CONFIRA:  "reasons" traz o motivo do bloqueio
       >>> anote  dossier_id

       Este é o coração do Marco 9: o animal foi barrado por uma regra
       versionada, com motivo explícito.


======== PARTE 2 — A CORREÇÃO NÃO APAGA (operador) ========

  2.1  POST /v1/livestock/treatments/<application_id>/corrections ... espera 201
       {{
         "applied_at": "{corrigido_em}",
         "dose": "2 mL / 50 kg"
       }}
       >>> CONFIRA: "application_id" é DIFERENTE do original
       >>> CONFIRA: "corrects_application_id" aponta para o original

       Não existe rota de edição. Corrigir cria registro novo, e o antigo
       permanece — você vai vê-lo na linha do tempo, no passo 3.2.


========== PARTE 3 — LEITURA (troque para o auditor) ==========

O botão "Logout" do Swagger não encerra a sessão do Keycloak. Para trocar de
usuário, abra uma JANELA ANÔNIMA em http://localhost:8000/docs e autorize como
{semeado.auditor_username}. (Ou saia em {keycloak_url}/realms/titan/account.)

  3.1  GET /v1/livestock/dossiers/<dossier_id> .......... espera 200
       >>> CONFIRA: "dossier_hash" presente
       >>> CONFIRA: document.vertical.namespace == "livestock"
       >>> CONFIRA: document.vertical.content.subject traz o animal
       >>> CONFIRA: document.vertical.content.withdrawal mostra a conta
       >>> CONFIRA: document.vertical.content.timeline traz o histórico

       Este JSON é a prova: quem o recebe consegue verificá-lo sem o Titan.

  3.2  GET /v1/livestock/animals/<animal_id>/timeline ... espera 200
       >>> CONFIRA: aparecem livestock.animal_registered,
                    livestock.treatment_applied (DUAS vezes) e core.decision
       >>> CONFIRA: uma das aplicações tem "superseded_by" preenchido

       As duas aplicações provam que a correção não apagou o corrigido.

  3.3  GET .../timeline?known_until={antes_do_tratamento}
       >>> CONFIRA: o tratamento NÃO aparece

       Este é o eixo de auditoria: reconstrói o que o Titan sabia naquele
       instante, e não o que aconteceu até ele.


============ PARTE 4 — AS NEGAÇÕES ============

  4.1  auditor -> POST /v1/livestock/medications ........ espera 403
       >>> CONFIRA: reason_code == "PERMISSAO_AUSENTE"
       Auditor não escreve.

  4.2  operador -> GET /v1/livestock/dossiers/<dossier_id> ... espera 403
       >>> CONFIRA: reason_code == "PERMISSAO_AUSENTE"
       A separação vale nos dois sentidos: quem opera não lê a prova.

  4.3  qualquer usuário, cabeçalho com a Org B ({org_b}) ... espera 403
       >>> CONFIRA: reason_code == "CONTEXTO_ORGANIZACIONAL_NEGADO"
       A negação não revela se o recurso existe do outro lado.

  4.4  sem "Authorize" (janela anônima, sem autorizar) ....... espera 401
       >>> CONFIRA: reason_code == "NAO_AUTENTICADO"
       401 é "não sei quem você é"; 403 é "sei, e você não pode".

  4.5  operador, sem preencher X-Titan-Organization-Id ....... espera 400
       >>> CONFIRA: reason_code == "ORGANIZACAO_NAO_INFORMADA"

  4.6  operador, POST /animals com "sex": "INEXISTENTE" ...... espera 422
       >>> CONFIRA: reason_code == "ENTRADA_INVALIDA" e a lista "errors"

  4.7  operador, POST /animals duas vezes com o mesmo SISBOV . espera 409
       Acrescente ao corpo do passo 1.1 e repita a chamada:
         "initial_identifier_type": "OFFICIAL_SISBOV",
         "initial_identifier_value": "BR12345678"
       >>> CONFIRA: a segunda devolve reason_code == "CONFLITO_DE_DOMINIO"

  4.8  operador, POST /medication-batches com medication_id inventado ... espera 404
       >>> CONFIRA: reason_code == "RECURSO_NAO_ENCONTRADO"

  4.9  operador, POST /treatments com "applied_at": "{no_futuro}" ... espera 409
       >>> CONFIRA: reason_code == "CONFLITO_DE_DOMINIO"


======== PARTE 5 — A SAÍDA DO REBANHO (volte ao operador) ========

Até o Passo 13.1 o animal não tinha fim: todo animal cadastrado permanecia
implicitamente vivo e presente, e um recall varreria animais mortos há anos.

  5.1  POST /v1/livestock/animals/<animal_id>/exit ...... espera 201
       {{
         "exit_type": "ABATE",
         "occurred_at": "{saida_em}",
         "reason": "Abate programado",
         "destination": "Frigorifico Central"
       }}
       Os tipos são MORTE, ABATE, VENDA e TRANSFERENCIA_DEFINITIVA.

  5.2  GET /v1/livestock/animals?limit=200 ............. espera 200
       >>> CONFIRA: o animal NÃO aparece mais

       A listagem passou a devolver o rebanho ativo. Quem lista animais quer o
       rebanho, e não o histórico inteiro desde a fundação da organização.

  5.3  GET /v1/livestock/animals?limit=200&incluir_saidos=true ... espera 200
       >>> CONFIRA: o animal reaparece, agora com o objeto "saida" preenchido

  5.4  GET /v1/livestock/animals/<animal_id> ........... espera 200
       >>> CONFIRA: "saida" vem preenchida sem precisar de parâmetro algum

       Sair do rebanho não é desaparecer: é justamente depois da saída que a
       auditoria acontece.

  5.5  POST /v1/livestock/treatments ................... espera 409
       {{
         "animal_id": "<animal_id>",
         "medication_batch_id": "<batch_id>",
         "applied_at": "{depois_da_saida}",
         "dose": "1 mL / 50 kg"
       }}
       >>> CONFIRA: reason_code == "CONFLITO_DE_DOMINIO"
       >>> CONFIRA: a mensagem cita a data da saída e o tipo ABATE

       Um boi abatido não é tratado depois. O critério é o instante em que o
       fato OCORREU, nunca o do registro.

  5.6  POST /v1/livestock/treatments ................... espera 201
       O mesmo corpo do 5.5, mudando só a data para antes da saída:
         "applied_at": "{antes_da_saida}"
       >>> CONFIRA: passa

       Lançar hoje um tratamento aplicado antes da saída é regularização de
       registro — o caso mais comum no campo. Recusá-lo apagaria o que de fato
       aconteceu, que é o oposto do que um registro append-only faz.

       Os passos 5.5 e 5.6 são o coração do Marco 13, do mesmo modo que o 1.5
       é o do Marco 9.

  5.7  POST /v1/livestock/animals/<animal_id>/exit ...... espera 409
       Repita o corpo do 5.1 com "exit_type": "VENDA".
       >>> CONFIRA: sair é terminal, e o banco recusa a segunda saída mesmo que
                    a conferência da aplicação falhasse


========= PARTE 6 — A GENEALOGIA (Passo 13.2) =========

Cadastre três animais novos e anote os identificadores:
  BEZERRO (MALE), DOADORA (FEMALE) e RECEPTORA (FEMALE).

  6.1  POST /v1/livestock/animals/<BEZERRO>/maternity ... espera 201
       {{
         "genetic_mother_id": "<DOADORA>",
         "gestational_mother_id": "<RECEPTORA>",
         "occurred_at": "{saida_em}",
         "confidence": "DECLARADO"
       }}
       >>> CONFIRA: a resposta traz DOIS vinculos, MAE_GENETICA e MAE_GESTACIONAL

       Com transferencia de embriao, quem forneceu o ovulo e quem gestou sao
       vacas diferentes, e ambas sao fato. Sem transferencia, basta omitir
       gestational_mother_id — e as duas relacoes sao gravadas do mesmo jeito,
       porque ausencia se declara e nao se infere.

  6.2  GET /v1/livestock/animals/<BEZERRO>/ancestry .... espera 200
       >>> CONFIRA: aparece a DOADORA
       >>> CONFIRA: a RECEPTORA nao aparece

       A linhagem sobe pela genetica. Quem gestou nao transmitiu genes, e
       inclui-la daria a arvore um ancestral que nao e.

  6.3  GET /v1/livestock/animals/<RECEPTORA>/reproduction ... espera 200
       >>> CONFIRA: o BEZERRO aparece — ela gestou

  6.4  GET /v1/livestock/animals/<RECEPTORA>/descendants .... espera 200
       >>> CONFIRA: lista VAZIA — nenhuma cria descende dela

       Os passos 6.3 e 6.4 sao a mesma vaca respondendo a duas perguntas
       diferentes. Colapsa-las e o erro que este passo existe para evitar.

  6.5  GET /v1/livestock/animals/<RECEPTORA>/timeline ... espera 200
       >>> CONFIRA: aparece livestock.parentage_registered

       O parto entra na vida da vaca. A relacao e o agregado do evento, e as
       duas pontas a citam — o fato nao e gravado duas vezes.

  6.6  POST /v1/livestock/animals/<BEZERRO>/paternity ... espera 201, tres vezes
       Cadastre tres touros e repita com cada um:
       {{
         "father_id": "<TOURO>",
         "occurred_at": "{saida_em}",
         "confidence": "DECLARADO"
       }}
       >>> CONFIRA: os tres sao aceitos

       E o touro do lote: monta natural com varios reprodutores, em que a
       paternidade so se resolve por DNA. Paternidade indeterminada e caso
       reconhecido, e nao erro a corrigir.

  6.7  POST /v1/livestock/animals/<BEZERRO>/paternity ... espera 409
       Um quarto touro, agora com "confidence": "DOCUMENTADO".
       >>> CONFIRA: reason_code == "CONFLITO_DE_DOMINIO"

       Quem tem registro de cobertura afirma UM pai. Admitir um segundo ao lado
       de um vinculo documentado transformaria prova em palpite.

  6.8  POST /v1/livestock/animals/<BEZERRO>/maternity ... espera 409
       Outra vaca qualquer como genetic_mother_id.
       >>> CONFIRA: duas maes geneticas vigentes sao contradicao, e nao dado
                    incompleto

  6.9  POST /v1/livestock/animals/<BEZERRO>/maternity ... espera 409
       Use um TOURO como genetic_mother_id.
       >>> CONFIRA: nomear alguem como mae e afirmar que e femea


=========== O QUE ISTO DEMONSTRA NO FIM ===========

  o animal foi bloqueado por uma regra versionada, com motivo;
  a correção acrescentou sem apagar o que estava errado;
  a prova é verificável por terceiro, sem acesso ao Titan;
  papéis diferentes têm alcances diferentes, nos dois sentidos;
  uma organização não enxerga a outra, e a negação não entrega pistas;
  o animal tem fim, e o fim fecha o futuro sem apagar o passado;
  a linhagem sobe por quem deu os genes, e o parto fica com quem pariu.

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
        duracao = admin.garantir_duracao_de_token(DURACAO_DO_TOKEN_SEGUNDOS)
        print(f"Token    : validade de {duracao}s no realm local de demonstracao")
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
