"""Roteiro do Corte 2B: leitura e revisão de captura SISBOV simulada.

python -m uv run --locked python -m apps.validacao.captura_externa_sisbov_simulada [--pausar]
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import create_engine, text

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import CLIENTE_DE_VALIDACAO, _ambiente, _descobrir_organizacao
from apps.validacao.runner import AMARELO, FIM, NEGRITO, Cliente, Requisicao, Resposta, Roteiro
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.livestock_domain.external_source_capture import ExternalSourceCaptureArtifact
from packages.livestock_infrastructure.persistence import (
    TransactionalExternalSourceCaptureArtifactRepository,
)
from packages.shared_kernel import OrganizationId, TypedId


def _exigir_preflight(operador: Cliente, database_url: str) -> None:
    """Falha cedo quando migration ou as permissões recém-semeadas faltam."""
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            table = connection.execute(
                text("SELECT to_regclass('core_audit.external_source_capture_association_reviews')")
            ).scalar_one()
    finally:
        engine.dispose()
    if table is None:
        raise SystemExit(
            "A migration da revisão de captura não está aplicada. Execute:\n"
            "  python -m uv run --locked alembic upgrade head"
        )
    probes = [
        operador.get("/v1/livestock/external-source-captures"),
        operador.post(
            "/v1/livestock/external-source-captures/00000000-0000-4000-8000-000000000000/reviews",
            {
                "candidate_animal_id": "00000000-0000-4000-8000-000000000000",
                "status": "NEEDS_MORE_EVIDENCE",
                "basis_code": "SONDA_DE_PERMISSAO",
            },
        ),
    ]
    if all(probe.status != 403 for probe in probes):
        return
    raise SystemExit(
        f"{AMARELO}O operador ainda não recebeu as permissões deste corte.{FIM}\n"
        "Os papéis guardam as permissões existentes quando foram semeados. Semeie de novo\n"
        "e reinicie a API com a operadora nova:\n"
        "  $env:TITAN_SEED_CONFIRM = '1'; python -m uv run --locked python -m apps.seed"
    )


def _registrar_fixture_captura(database_url: str, organization: str) -> str:
    """Insere só o artefato sintético necessário para exercitar a API de review.

    A API deliberadamente não tem endpoint de captura: ela não recebe material
    externo nem dispara HTTP. Esta preparação local usa somente a projeção
    allowlisted e não cria Fact, Evidence, coverage ou associação no Animal.
    """
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            organization_id = OrganizationId.parse(organization)
            set_local_organization_context(connection, organization_id)
            artifact = ExternalSourceCaptureArtifact.create(
                organization_id=organization_id,
                contract_version="SISBOV_SIMULATOR_CAPTURE/v1",
                resource_kind="animal",
                request_scope_digest="a" * 64,
                transport_outcome="SUCCEEDED",
                response_status_code=200,
                response_digest="b" * 64,
                captured_at=datetime.now(UTC),
                parser_name="SisbovSimulatorParser",
                parser_version="1",
                parsing_diagnostic_code=None,
                recorded_by=TypedId.new("system"),
                review_projection={
                    "resource_kind": "animal",
                    "external_reference": f"SIM-{uuid4().hex[:16]}",
                    "declared_fields": {"statusAnimal": "ATIVO"},
                },
            )
            TransactionalExternalSourceCaptureArtifactRepository(connection).save(artifact)
            return str(artifact.artifact_id.value)
    finally:
        engine.dispose()


def _roteiro(operador: Cliente, auditor: Cliente, database_url: str) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("Corte 2B — captura SISBOV simulada e revisão humana", diario=operador.diario)

    def criar_animal_e_fixture() -> Resposta:
        property_response = operador.get("/v1/livestock/properties?limit=1")
        if property_response.status != 200 or not property_response["items"]:
            return property_response
        response = operador.post(
            "/v1/livestock/animals",
            {"birth_property_id": property_response["items"][0]["property_id"], "sex": "FEMALE"},
        )
        if response.status == 201:
            ids["animal_id"] = str(response["animal_id"])
            ids["capture_artifact_id"] = _registrar_fixture_captura(
                database_url, operador.organization_id
            )
        return response

    roteiro.passo(
        "1",
        "Cria Animal fictício e prepara captura simulada minimizada",
        criar_animal_e_fixture,
        201,
        conferir=lambda _: (
            None if ids.get("capture_artifact_id") else "a captura sintética não foi preparada"
        ),
        porque=(
            "A captura é preparada pelo serviço interno; a API não aceita material externo "
            "nem consulta o simulador."
        ),
    )
    roteiro.passo(
        "2",
        "Auditor lê a projeção allowlisted sem review",
        lambda: auditor.get("/v1/livestock/external-source-captures"),
        200,
        conferir=lambda response: (
            None
            if any(
                item["artifact_id"] == ids["capture_artifact_id"]
                and item["review_projection"] is not None
                and item["reviews"] == []
                for item in response["items"]
            )
            else "a captura ou sua projeção minimizada não apareceu"
        ),
        porque=(
            "Leitura mostra somente a projeção canônica; digest e resposta externa "
            "bruta não são expostos."
        ),
    )
    roteiro.passo(
        "3",
        "Operador registra review de candidato local",
        lambda: operador.post(
            f"/v1/livestock/external-source-captures/{ids['capture_artifact_id']}/reviews",
            {
                "candidate_animal_id": ids["animal_id"],
                "status": "CONFIRMED_CANDIDATE",
                "basis_code": "IDENTIFICADOR_SISBOV_CONFERIDO",
            },
        ),
        201,
        conferir=lambda response: (
            None
            if response["candidate_animal_id"] == ids["animal_id"]
            and response["status"] == "CONFIRMED_CANDIDATE"
            else "a review não preservou candidato e status"
        ),
        porque=(
            "Confirmar um candidato cria somente uma review append-only; não altera "
            "a identidade do Animal."
        ),
    )
    roteiro.passo(
        "4",
        "Auditor recupera a review preservada",
        lambda: auditor.get("/v1/livestock/external-source-captures"),
        200,
        conferir=lambda response: (
            None
            if any(
                item["artifact_id"] == ids["capture_artifact_id"]
                and item["reviews"]
                and item["reviews"][0]["candidate_animal_id"] == ids["animal_id"]
                for item in response["items"]
            )
            else "a review não foi recuperada pelo leitor"
        ),
        porque="A auditoria lê a decisão humana sem ganhar permissão para escrevê-la.",
    )
    roteiro.passo(
        "5",
        "Auditor não pode registrar outra review",
        lambda: auditor.post(
            f"/v1/livestock/external-source-captures/{ids['capture_artifact_id']}/reviews",
            {
                "candidate_animal_id": ids["animal_id"],
                "status": "NEEDS_MORE_EVIDENCE",
                "basis_code": "TESTE_NEGATIVO_DE_PERMISSAO",
            },
        ),
        403,
        porque="Ler o artefato não concede capacidade de produzir uma afirmação humana auditável.",
    )
    return roteiro


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida leitura e review de captura SISBOV simulada."
    )
    parser.add_argument("--pausar", action="store_true")
    parser.add_argument("--organizacao", default="")
    options = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    database_url = os.environ.get("TITAN_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Defina TITAN_DATABASE_URL antes do roteiro.")
    api = _ambiente("TITAN_API_URL", "http://localhost:8000")
    keycloak = _ambiente("TITAN_OIDC_BASE_URL", "http://localhost:8080").rstrip("/")
    realm = _ambiente("TITAN_OIDC_REALM", "titan")
    organization = options.organizacao or _descobrir_organizacao(database_url)
    admin = AdminKeycloak.autenticar(
        base_url=keycloak,
        realm=realm,
        usuario=_ambiente("TITAN_OIDC_ADMIN_USERNAME", "titan_admin"),
        senha=_ambiente("TITAN_OIDC_ADMIN_PASSWORD", "titan_oidc_local_admin_password"),
    )
    admin.garantir_cliente_de_validacao(CLIENTE_DE_VALIDACAO)
    diary: list[Requisicao] = []

    def cliente(username: str, rotulo: str) -> Cliente:
        return Cliente(
            base_url=api,
            token=admin.token_de_usuario(
                client_id=CLIENTE_DE_VALIDACAO, username=username, senha=SENHA_DEMONSTRACAO
            ),
            organization_id=organization,
            rotulo=rotulo,
            diario=diary,
        )

    operador = cliente("titan_operador", "operador")
    auditor = cliente("titan_auditor", "auditor")
    _exigir_preflight(operador, database_url)
    print(
        f"{NEGRITO}Preflight{FIM}\n"
        f"  API: {api}\n  Keycloak: {keycloak}\n  Organization: {organization}\n"
        "  Fixture: captura SIMULATED allowlisted, inserida localmente pelo serviço interno"
    )
    return _roteiro(operador, auditor, database_url).executar(pausar=options.pausar)


if __name__ == "__main__":
    raise SystemExit(main())
