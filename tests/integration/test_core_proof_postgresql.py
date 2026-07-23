"""Prova completa do Titan Core contra PostgreSQL real (Passo 7.10).

Encadeia o cenário fictício e genérico exigido pelo plano, de ponta a ponta:

    autenticação → Organization → evento → evidência → genealogia → regra →
    avaliação → decisão → não conformidade → recall → dossiê → sincronização

O cenário não usa vocabulário de nenhuma vertical: os sujeitos são `lote`,
`insumo` e `remessa`, e a política é genérica. O Core não conhece Livestock, e
uma prova escrita com termos de gado esconderia exatamente esse acoplamento.

Os quatro critérios de validação manual do Passo 7.10 são testes próprios:
substituir providers falsos sem alterar o Core, adulterar cópias para testar
integridade, repetir operações e comprovar isolamento entre duas Organizations.
"""

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Connection, create_engine, text

from packages.core_application.crypto import KeyManagementService
from packages.core_application.decision_service import DecisionService
from packages.core_application.dossier_service import DossierService
from packages.core_application.evaluation_service import (
    PolicyEvaluationService,
    RuleEvaluationEngine,
)
from packages.core_application.evidence_service import EvidenceService
from packages.core_application.nonconformity_service import NonConformityService
from packages.core_application.organization_context import OrganizationContextService
from packages.core_application.policy_service import PolicyService
from packages.core_application.recall_service import RecallService
from packages.core_application.relation_service import RelationService
from packages.core_application.rule_service import RuleService
from packages.core_application.synchronization_service import SynchronizationService
from packages.core_application.verification_service import VerificationBundleService
from packages.core_domain import (
    AuthenticatedPrincipal,
    ExternalIdentity,
    Membership,
    MembershipRoleAssignment,
    Organization,
    Permission,
    PrincipalType,
    Role,
    User,
)
from packages.core_domain.crypto import (
    CryptographicProfile,
    CryptographicSignature,
    KeyIdentifier,
)
from packages.core_domain.decision import DecisionResult
from packages.core_domain.dossier import compute_dossier_hash
from packages.core_domain.events import CanonicalPayload, DomainEvent
from packages.core_domain.evidence import (
    ConfidenceLevel,
    ConfidenceTier,
    Source,
    SourceType,
    VerificationOutcome,
)
from packages.core_domain.facts import Fact, FactSnapshot
from packages.core_domain.nonconformity import NonConformityStatus
from packages.core_domain.recall import (
    RecallDirection,
    RecallLimitReason,
    RecallMode,
    RecallRequest,
    RecallStatus,
)
from packages.core_domain.relations import UniversalRelation
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_domain.synchronization import (
    DeviceClockReading,
    OfflineOperation,
    SynchronizationBatch,
    SynchronizationBatchState,
    SynchronizationResultStatus,
    TimeConfidenceLevel,
)
from packages.core_domain.verification import (
    BundleVerifier,
    SignatureMaterial,
    VerificationBundle,
    VerificationStatus,
)
from packages.core_infrastructure.crypto import SoftwareKeyProvider, SoftwareSigningProvider
from packages.core_infrastructure.organization_context import (
    PostgresqlIdentityAndAccessReader,
)
from packages.core_infrastructure.persistence import (
    AuthorizationRepository,
    ExternalIdentityRepository,
    MembershipRepository,
    OrganizationRepository,
    UserRepository,
    set_local_organization_context,
)
from packages.core_infrastructure.persistence.crypto import TransactionalKeyRegistryRepository
from packages.core_infrastructure.persistence.decision import TransactionalDecisionRepository
from packages.core_infrastructure.persistence.dossier import TransactionalDossierRepository
from packages.core_infrastructure.persistence.evaluation import TransactionalEvaluationRepository
from packages.core_infrastructure.persistence.events import DomainEventRepository
from packages.core_infrastructure.persistence.evidence import TransactionalEvidenceRepository
from packages.core_infrastructure.persistence.nonconformity import (
    TransactionalNonConformityRepository,
)
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.recall import TransactionalRecallRepository
from packages.core_infrastructure.persistence.relations import TransactionalRelationRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.synchronization import (
    TransactionalSynchronizationRepository,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference
from packages.shared_kernel.temporal import FixedClock, RecordTimestamps

T0 = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)

# Todas as tabelas tocadas pelo cenário. O teste de isolamento percorre esta
# lista inteira: provar o isolamento de uma tabela e presumir o das outras já
# seria a falha que o Passo 7.10 existe para descartar.
CORE_AUDIT_TABLES = (
    "domain_events",
    "evidences",
    "relations",
    "policies",
    "rules",
    "evaluations",
    "decisions",
    "nonconformities",
    "recalls",
    "dossiers",
    "offline_operations",
    "synchronization_results",
    "synchronization_batches",
)


@pytest.fixture
def db_connection() -> Iterator[Connection]:
    db_url = os.getenv(
        "TITAN_DATABASE_URL",
        "postgresql+psycopg://titan:titan_local_dev_password@127.0.0.1:5432/titan",
    )
    engine = create_engine(db_url, pool_pre_ping=True)
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            # O cenário inteiro é descartado: a prova não deixa resíduo no banco.
            transaction.rollback()
    engine.dispose()


def _ref(org: OrganizationId, entity_type: str, value: TypedId | None = None) -> UniversalReference:
    return UniversalReference(
        target_id=value or TypedId.new(entity_type),
        organization_id=org,
        contract_version=1,
    )


@dataclass
class CoreProof:
    """Resultado do cenário completo, para os testes derivados inspecionarem."""

    connection: Connection
    organization_id: OrganizationId
    other_organization_id: OrganizationId
    subject_id: TypedId
    evidence_id: TypedId
    event_id: TypedId
    decision_id: TypedId
    dossier_hash: str
    produced: dict[str, object] = field(default_factory=dict)


def _bootstrap_identity(
    connection: Connection, now: datetime
) -> tuple[Organization, Organization, AuthenticatedPrincipal, OrganizationContextService]:
    """Autenticação e Organization: o primeiro elo da cadeia.

    A Organization operadora é dona do User global; a Organization atuante é onde
    o vínculo e as Permissions vivem. Sem esse contexto, nenhum passo seguinte tem
    onde gravar.
    """
    operator = Organization.create()
    acting = Organization.create()
    for organization in (operator, acting):
        set_local_organization_context(connection, organization.organization_id)
        OrganizationRepository(connection).add(organization)

    permission = Permission.create(
        operator_organization_id=operator.organization_id, code="CORE.PROVA"
    )
    AuthorizationRepository(connection).add_permission(permission)

    set_local_organization_context(connection, operator.organization_id)
    user = User.create(platform_operator_organization_id=operator.organization_id)
    UserRepository(connection).add(user)

    principal = AuthenticatedPrincipal(
        issuer="https://issuer.example/realms/titan",
        subject=f"subject-{uuid4().hex[:8]}",
        principal_type=PrincipalType.USER,
        authenticated_at=now,
        client_id="titan-swagger",
        technical_scopes=frozenset({"openid"}),
    )
    ExternalIdentityRepository(connection).add(
        ExternalIdentity.link_user(
            operator_organization_id=operator.organization_id,
            issuer=principal.issuer,
            subject=principal.subject,
            user_id=user.user_id,
            linked_at=now,
            linked_by_actor_id=TypedId.new("actor"),
        )
    )

    set_local_organization_context(connection, acting.organization_id)
    membership = Membership.create(
        user_id=user.user_id,
        organization_id=acting.organization_id,
        valid_from=now - timedelta(days=1),
        valid_until=None,
        origin_reference=TypedId.new("membership_invitation"),
        granted_by_actor_id=TypedId.new("actor"),
    )
    MembershipRepository(connection).add(membership)
    role = Role.create(
        organization_id=acting.organization_id,
        name="Operador",
        permission_ids=(permission.permission_id,),
    )
    authorization = AuthorizationRepository(connection)
    authorization.add_role(role)
    authorization.assign_role(
        MembershipRoleAssignment.create(
            membership_id=membership.membership_id,
            role_id=role.role_id,
            organization_id=acting.organization_id,
            valid_from=now,
            valid_until=None,
            granted_by_actor_id=TypedId.new("actor"),
        )
    )

    service = OrganizationContextService(
        PostgresqlIdentityAndAccessReader(connection, operator.organization_id)
    )
    return operator, acting, principal, service


def _run_full_scenario(connection: Connection) -> CoreProof:
    """Executa a cadeia completa e devolve os artefatos produzidos."""
    operator, acting, principal, context_service = _bootstrap_identity(connection, T0)
    org = acting.organization_id

    # ---- 1. Autenticação → OrganizationContext ---------------------------
    context = context_service.build(principal=principal, requested_organization_id=org, instant=T0)
    assert context.organization_id == org
    assert "CORE.PROVA" in context.permission_codes

    set_local_organization_context(connection, org)
    actor = _ref(org, "actor", context.actor_id)
    subject = _ref(org, "lote")

    # ---- 2. Evento -------------------------------------------------------
    clock = FixedClock(T0)
    event = DomainEvent(
        event_id=TypedId.new("domain_event"),
        organization_id=org,
        aggregate_reference=subject,
        aggregate_version=1,
        event_type="prova.lote_registrado",
        event_version=1,
        timestamps=RecordTimestamps.capture(occurred_at=T0, clock=clock),
        actor_reference=actor,
        source_reference=_ref(org, "source"),
        correlation_id=TypedId.new("correlation"),
        causation_id=None,
        payload=CanonicalPayload(
            schema="prova.lote_registrado", version=1, value={"identificador": "LOTE-001"}
        ),
    )
    DomainEventRepository(connection).append(event)

    # ---- 3. Evidência: registrar, assinar com provider falso e verificar --
    key_provider = SoftwareKeyProvider()
    key_registry = TransactionalKeyRegistryRepository(connection)
    key = KeyManagementService(registry=key_registry).register_key(
        organization_id=org,
        purpose="Integridade e Assinatura de Evidências",
        public_key_fingerprint="fingerprint-de-teste",
    )
    key_provider.register_key(key.key_identifier, b"segredo-exclusivamente-ficticio")

    evidence_service = EvidenceService(
        repository=TransactionalEvidenceRepository(connection),
        signing_provider=SoftwareSigningProvider(key_provider=key_provider),
        key_registry=key_registry,
    )
    evidence = evidence_service.register_evidence(
        organization_id=org,
        source=Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT),
        author_reference=actor,
        content=b"conteudo ficticio do laudo",
        confidence_level=ConfidenceLevel(
            tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado ao registro."
        ),
    )
    evidence = evidence_service.sign_evidence(
        evidence_id=evidence.evidence_id, profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE
    )
    evidence = evidence_service.verify_evidence(
        evidence_id=evidence.evidence_id,
        verifier_reference=actor,
        outcome=VerificationOutcome.VERIFIED,
        notes="Conferido contra o documento original fictício.",
    )
    assert evidence.signature is not None

    # ---- 4. Genealogia: insumo → lote → remessa --------------------------
    relation_service = RelationService(repository=TransactionalRelationRepository(connection))
    insumo = _ref(org, "insumo")
    remessa = _ref(org, "remessa")
    confianca = ConfidenceLevel(tier=ConfidenceTier.DOCUMENTED, reason="Vínculo documentado.")
    for origem, destino in ((insumo, subject), (subject, remessa)):
        relation_service.register_relation(
            UniversalRelation.create(
                organization_id=org,
                source_reference=origem,
                target_reference=destino,
                relation_type="transformacao",
                created_at=T0,
                confidence=confianca,
                valid_from=T0,
                created_by_event=event.event_id,
                evidence_references=(_ref(org, "evidence", evidence.evidence_id),),
            )
        )

    # ---- 5. Regra --------------------------------------------------------
    policy_service = PolicyService(repository=TransactionalPolicyRepository(connection))
    rule_service = RuleService(repository=TransactionalRuleRepository(connection))
    policy = policy_service.publish_policy(
        policy_service.create_draft(
            organization_id=org, code="pol-prova", name="Política genérica de prova"
        ).policy_id
    )
    rule = rule_service.create_rule(
        policy_id=policy.policy_id,
        organization_id=org,
        code="rule-conformidade",
        name="Laudo aprovado",
        severity=SeverityLevel.BLOCKING,
        conditions=(
            RuleCondition(
                fact_type="prova.laudo",
                payload_key="resultado",
                operator=ComparisonOperator.EQUALS,
                expected_value="aprovado",
            ),
        ),
        corrective_action="Reemitir o laudo com resultado conclusivo.",
    )

    # ---- 6. Avaliação sobre fatos ligados à evidência --------------------
    evidence_reference = _ref(org, "evidence", evidence.evidence_id)
    snapshot = FactSnapshot.create(
        organization_id=org,
        target_id=subject.target_id,
        as_of=T0,
        facts=[
            Fact.create(
                fact_type="prova.laudo",
                payload={"resultado": "reprovado"},
                observed_at=T0,
                source_reference=evidence_reference,
            )
        ],
    )
    evaluation = PolicyEvaluationService(engine=RuleEvaluationEngine()).evaluate_policy(
        policy=policy, rules=[rule], snapshot=snapshot, purpose="PROVA_DO_CORE"
    )
    TransactionalEvaluationRepository(connection=connection).save(evaluation)
    assert evaluation.is_reproducible()

    # ---- 7. Decisão explicável ------------------------------------------
    decision = DecisionService().decide(evaluation)
    TransactionalDecisionRepository(connection=connection).save(decision)
    assert decision.result is DecisionResult.REJEITADA
    assert decision.reasons, "Decisão sem razão não é explicável."

    # ---- 8. Não conformidade --------------------------------------------
    nonconformity_service = NonConformityService(
        repository=TransactionalNonConformityRepository(connection)
    )
    nonconformities = nonconformity_service.open_from_evaluation(evaluation)
    assert len(nonconformities) == 1
    # O ciclo de vida é respeitado passo a passo: detectada → classificada →
    # atribuída. Pular etapa é recusado pelo próprio domínio.
    nonconformity_service.classify(
        nonconformity_id=nonconformities[0].nonconformity_id,
        occurred_at=T0 + timedelta(minutes=1),
        corrective_action="Reemitir o laudo com resultado conclusivo.",
    )
    nonconformity = nonconformity_service.assign(
        nonconformity_id=nonconformities[0].nonconformity_id,
        responsible_reference=actor,
        due_date=T0 + timedelta(days=7),
        occurred_at=T0 + timedelta(minutes=2),
    )
    assert nonconformity.status is not NonConformityStatus.ENCERRADA

    # ---- 9. Recall sobre a genealogia -----------------------------------
    recall_service = RecallService(
        relations=TransactionalRelationRepository(connection),
        result_repository=TransactionalRecallRepository(connection),
    )
    # Travessia limpa: sem lacuna, o resultado é conclusivo.
    retrospectiva = recall_service.execute(
        RecallRequest(
            organization_id=org,
            subject_reference=subject,
            direction=RecallDirection.RETROSPECTIVA,
            mode=RecallMode.SIMULACAO,
            at_time=T0 + timedelta(hours=1),
        ),
        executed_at=T0 + timedelta(hours=1),
    )
    assert {c.reached.target_id for c in retrospectiva.paths} == {insumo.target_id}
    assert retrospectiva.gaps == ()
    assert retrospectiva.status is RecallStatus.CONCLUSIVO

    # Travessia nos dois sentidos: alcança as duas pontas e, ao reencontrar o
    # sujeito inicial, declara a lacuna em vez de omiti-la. É a lacuna declarada
    # que rebaixa o resultado inteiro a inconclusivo — desconhecimento nunca
    # vira silêncio, mesmo quando o reencontro é inofensivo.
    recall = recall_service.execute(
        RecallRequest(
            organization_id=org,
            subject_reference=subject,
            direction=RecallDirection.AMBAS,
            mode=RecallMode.INCIDENTE,
            at_time=T0 + timedelta(hours=1),
        ),
        executed_at=T0 + timedelta(hours=1),
    )
    alcancados = {caminho.reached.target_id for caminho in recall.paths}
    assert insumo.target_id in alcancados, "Recall retrospectivo não alcançou a origem."
    assert remessa.target_id in alcancados, "Recall prospectivo não alcançou o destino."
    assert {lacuna.reason for lacuna in recall.gaps} == {RecallLimitReason.CICLO_DETECTADO}
    assert recall.status is RecallStatus.INCONCLUSIVO

    # ---- 10. Dossiê autocontido e pacote de verificação -------------------
    dossier_repo = TransactionalDossierRepository(connection=connection)
    dossier = DossierService(repository=dossier_repo).build_and_store(
        decision=decision, evaluation=evaluation, policy=policy, rules=[rule]
    )
    assert dossier.verify()

    # O pacote só é declarado válido com assinatura, política de verificação e
    # âncora de confiança externa. Sem elas o veredito é INDETERMINADO, nunca
    # válido por omissão.
    bundle = VerificationBundleService().build_from_dossier(
        dossier=dossier,
        audience="AUDITORIA_EXTERNA",
        created_at=T0 + timedelta(hours=2),
        signature=SignatureMaterial(
            key_id="chave-da-prova",
            algorithm="sha256",
            profile="INSTITUTIONAL_SIGNATURE",
            signed_digest="",
            signature_value="assinatura-exclusivamente-ficticia",
            signed_at=T0 + timedelta(hours=2),
            certificate_chain=("cert-emissor-ficticio",),
            revocation_material=("crl-instante-de-referencia",),
        ),
        verification_policy={"perfil_minimo": "INSTITUTIONAL_SIGNATURE"},
        profiles=("INSTITUTIONAL_SIGNATURE",),
    )
    ancoras = {"chave-da-prova": "assinatura-exclusivamente-ficticia"}
    verifier = BundleVerifier()
    report = verifier.verify(
        bundle=bundle, verified_at=T0 + timedelta(hours=3), trust_anchors=ancoras
    )
    assert report.status is VerificationStatus.VALIDA, report.failures

    sem_ancora = verifier.verify(bundle=bundle, verified_at=T0 + timedelta(hours=3))
    assert sem_ancora.status is VerificationStatus.INDETERMINADA

    # ---- 11. Sincronização produz efeito oficial na mesma cadeia ---------
    sync_repository = TransactionalSynchronizationRepository(connection=connection)
    device = _ref(org, "device")
    aplicadas: list[TypedId] = []

    def efeito(operation: OfflineOperation) -> tuple[UniversalReference, ...]:
        """A operação offline vira uma relação real da genealogia."""
        destino = _ref(org, "remessa")
        relacao = UniversalRelation.create(
            organization_id=org,
            source_reference=remessa,
            target_reference=destino,
            relation_type="expedicao",
            created_at=T0,
            confidence=confianca,
            valid_from=T0,
        )
        relation_service.register_relation(relacao)
        aplicadas.append(operation.operation_id)
        return (_ref(org, "relation", relacao.relation_id),)

    sync_service = SynchronizationService(repository=sync_repository, effect_handler=efeito)
    operation = OfflineOperation(
        operation_id=TypedId.new("offline_operation"),
        organization_id=org,
        device_reference=device,
        actor_reference=actor,
        semantic_identity="prova.expedicao:001",
        idempotency_key="prova-expedicao-001",
        operation_type="prova.expedicao",
        contract_version=1,
        local_sequence=1,
        clock=DeviceClockReading(
            client_observed_at=T0,
            claimed_occurred_at=T0 - timedelta(minutes=20),
            timezone_name="America/Sao_Paulo",
            confidence=TimeConfidenceLevel.SINCRONIZADO_COM_SERVIDOR,
            last_server_contact_at=T0 - timedelta(hours=1),
        ),
        payload=CanonicalPayload(
            schema="prova.expedicao", version=1, value={"destino": "REMESSA-001"}
        ),
    )
    batch = SynchronizationBatch.create(
        organization_id=org,
        device_reference=device,
        operations=(operation,),
        created_at_device=T0,
    )
    batch_result = sync_service.receive_batch(batch, (operation,), T0 + timedelta(hours=4))
    assert batch_result.state is SynchronizationBatchState.PROCESSADO
    assert aplicadas == [operation.operation_id]

    return CoreProof(
        connection=connection,
        organization_id=org,
        other_organization_id=operator.organization_id,
        subject_id=subject.target_id,
        evidence_id=evidence.evidence_id,
        event_id=event.event_id,
        decision_id=decision.decision_id,
        dossier_hash=dossier.dossier_hash,
        produced={
            "dossier": dossier,
            "bundle": bundle,
            "batch": batch,
            "operation": operation,
            "sync_service": sync_service,
            "applied": aplicadas,
            "evidence_service": evidence_service,
            "key": key,
        },
    )


def test_cadeia_completa_do_core(db_connection: Connection) -> None:
    """Autenticação → … → sincronização, com cada elo alimentando o seguinte."""
    proof = _run_full_scenario(db_connection)
    assert proof.dossier_hash
    assert proof.decision_id.entity_type == "decision"


def test_repetir_operacoes_nao_duplica_efeito(db_connection: Connection) -> None:
    """Critério do plano: repetir operações."""
    proof = _run_full_scenario(db_connection)
    sync_service = proof.produced["sync_service"]
    batch = proof.produced["batch"]
    operation = proof.produced["operation"]
    aplicadas = proof.produced["applied"]
    assert isinstance(sync_service, SynchronizationService)
    assert isinstance(batch, SynchronizationBatch)
    assert isinstance(operation, OfflineOperation)
    assert isinstance(aplicadas, list)

    antes = list(aplicadas)
    repetido = sync_service.receive_batch(batch, (operation,), T0 + timedelta(hours=5))

    assert aplicadas == antes, "O reenvio repetiu o efeito oficial."
    assert repetido.counts[SynchronizationResultStatus.ACEITA] == 1

    repository = TransactionalSynchronizationRepository(connection=db_connection)
    recuperado = repository.get_result(operation.operation_id)
    assert recuperado is not None
    assert "RESULTADO_RECUPERADO" in recuperado.reason_codes


def test_adulterar_copias_quebra_a_integridade(db_connection: Connection) -> None:
    """Critério do plano: adulterar cópias para testar integridade.

    A adulteração é feita na cópia exportada, não no banco: é assim que o material
    viaja, e é aí que a verificação externa precisa recusá-lo.
    """
    proof = _run_full_scenario(db_connection)
    dossier = proof.produced["dossier"]
    bundle = proof.produced["bundle"]

    exportado = json.loads(json.dumps(dossier.document))  # type: ignore[attr-defined]
    assert compute_dossier_hash(exportado) == proof.dossier_hash

    # Inverter a conclusão é a adulteração mais tentadora, e a que mais importa pegar.
    adulterado = json.loads(json.dumps(exportado))
    adulterado["decision"]["result"] = "aprovada"
    assert compute_dossier_hash(adulterado) != proof.dossier_hash

    # Trocar o fato que sustenta a reprovação também precisa quebrar o hash.
    outro = json.loads(json.dumps(exportado))
    outro["facts"]["facts"][0]["payload"]["resultado"] = "aprovado"
    assert compute_dossier_hash(outro) != proof.dossier_hash

    # O pacote de verificação recusa componente adulterado sem consultar o Titan.
    assert isinstance(bundle, VerificationBundle)
    componente = bundle.payloads["dossier.json"]
    adulterado_bytes = componente.replace(b"rejeitada", b"aprovadaX", 1)
    assert adulterado_bytes != componente
    # O manifesto continua o original: é exatamente esse descasamento entre o
    # digest declarado e os bytes que viajam que a verificação precisa pegar.
    pacote_adulterado = VerificationBundle(
        manifest=bundle.manifest,
        payloads={**bundle.payloads, "dossier.json": adulterado_bytes},
        signature=bundle.signature,
    )
    relatorio = BundleVerifier().verify(
        bundle=pacote_adulterado,
        verified_at=T0 + timedelta(hours=3),
        trust_anchors={"chave-da-prova": "assinatura-exclusivamente-ficticia"},
    )
    assert relatorio.status is VerificationStatus.INVALIDA
    assert relatorio.failures


def test_substituir_provider_falso_nao_altera_o_core(db_connection: Connection) -> None:
    """Critério do plano: substituir providers falsos sem alterar o Core.

    O mesmo `EvidenceService` — mesma classe, mesmo código — assina com dois
    provedores diferentes. Se o Core precisasse mudar para trocar de provedor, a
    porta não seria uma porta.
    """
    proof = _run_full_scenario(db_connection)
    org = proof.organization_id
    key = proof.produced["key"]
    set_local_organization_context(db_connection, org)

    class ProviderAlternativo:
        """Segundo provedor, com algoritmo próprio e nenhum vínculo com o Core."""

        def __init__(self) -> None:
            self.chamadas = 0

        def sign(
            self,
            content_hash: bytes,
            key_identifier: KeyIdentifier,
            profile: CryptographicProfile,
        ) -> CryptographicSignature:
            self.chamadas += 1
            return CryptographicSignature(
                signature_id=TypedId.new("signature"),
                profile=profile,
                algorithm="ED25519",
                raw_signature=b"assinatura-ficticia-do-provedor-alternativo",
                key_identifier=key_identifier,
                signed_at=T0,
            )

    alternativo = ProviderAlternativo()
    servico = EvidenceService(
        repository=TransactionalEvidenceRepository(db_connection),
        signing_provider=alternativo,
        key_registry=TransactionalKeyRegistryRepository(db_connection),
    )
    evidencia = servico.register_evidence(
        organization_id=org,
        source=Source(source_id=TypedId.new("source"), source_type=SourceType.DOCUMENT),
        author_reference=_ref(org, "actor"),
        content=b"outro conteudo ficticio",
        confidence_level=ConfidenceLevel(
            tier=ConfidenceTier.DOCUMENTED, reason="Documento anexado."
        ),
    )
    assinada = servico.sign_evidence(
        evidence_id=evidencia.evidence_id, profile=CryptographicProfile.INSTITUTIONAL_SIGNATURE
    )

    assert alternativo.chamadas == 1
    assert assinada.signature is not None
    assert assinada.signature.algorithm == "ED25519"
    # A chave continua sendo a registrada pelo Core, não uma escolhida pelo provedor.
    assert assinada.signature.key_identifier.key_id == key.key_identifier.key_id  # type: ignore[attr-defined]


def test_isolamento_entre_duas_organizations(db_connection: Connection) -> None:
    """Critério do plano: comprovar isolamento entre duas Organizations.

    Percorre **todas** as tabelas do cenário sob uma role sem `BYPASSRLS`, no
    contexto da outra Organization. O usuário `titan` é superusuário e ignora RLS,
    então provar isolamento com ele não provaria nada.
    """
    proof = _run_full_scenario(db_connection)
    outra = proof.other_organization_id

    role_name = f"titan_proof_rls_{uuid4().hex[:12]}"
    quoted_role = db_connection.engine.dialect.identifier_preparer.quote(role_name)
    db_connection.execute(
        text(
            f"CREATE ROLE {quoted_role} "
            "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    )
    db_connection.execute(text(f"GRANT USAGE ON SCHEMA core_audit TO {quoted_role}"))
    for tabela in CORE_AUDIT_TABLES:
        db_connection.execute(text(f"GRANT SELECT ON core_audit.{tabela} TO {quoted_role}"))
    db_connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
    db_connection.execute(
        text("SELECT set_config('titan.organization_id', :org_id, true)"),
        {"org_id": str(outra.value)},
    )

    try:
        for tabela in CORE_AUDIT_TABLES:
            visiveis = db_connection.execute(
                text(f"SELECT count(*) AS total FROM core_audit.{tabela}")  # noqa: S608
            ).scalar_one()
            assert visiveis == 0, (
                f"A tabela core_audit.{tabela} vazou {visiveis} registro(s) "
                "da Organization do cenário para outra Organization."
            )
    finally:
        db_connection.execute(text("RESET ROLE"))
        db_connection.execute(text(f"DROP OWNED BY {quoted_role}"))
        db_connection.execute(text(f"DROP ROLE {quoted_role}"))
