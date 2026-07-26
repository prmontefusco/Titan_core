"""Roteiro executavel da matriz de elegibilidade por mercado (ADR-0044).

python -m uv run --locked python -m apps.validacao.matriz_elegibilidade_mercados
python -m uv run --locked python -m apps.validacao.matriz_elegibilidade_mercados --pausar
"""

import argparse
import os
import sys
from uuid import uuid4

from sqlalchemy import create_engine

from apps.seed.__main__ import SENHA_DEMONSTRACAO
from apps.seed.keycloak import AdminKeycloak
from apps.validacao.__main__ import (
    CLIENTE_DE_VALIDACAO,
    _ambiente,
    _descobrir_organizacao,
)
from apps.validacao.runner import AMARELO, CINZA, FIM, NEGRITO, Cliente, Requisicao, Roteiro
from packages.core_application.policy_service import PolicyService
from packages.core_application.rule_governance_service import RuleGovernanceService
from packages.core_domain.rule import ComparisonOperator, RuleCondition, SeverityLevel
from packages.core_domain.rule_governance import RuleSourceType
from packages.core_infrastructure.persistence import set_local_organization_context
from packages.core_infrastructure.persistence.policy import TransactionalPolicyRepository
from packages.core_infrastructure.persistence.rule import TransactionalRuleRepository
from packages.core_infrastructure.persistence.rule_governance import (
    TransactionalRuleAdoptionRepository,
    TransactionalRuleIdentityRepository,
    TransactionalRuleTimelineRepository,
)
from packages.livestock_application.eligibility import (
    ELIGIBILITY_RULE_ADOPTION_SCOPE,
    ELIGIBILITY_RULE_CODE,
)
from packages.livestock_application.market_eligibility import (
    DEFAULT_MARKET_PROFILES,
    TRACEABILITY_RULE_CODE,
)
from packages.shared_kernel import OrganizationId, TypedId, UniversalReference


def _preparar_regras_de_mercado(database_url: str, organizacao: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as conexao, conexao.begin():
            organization_id = OrganizationId.parse(organizacao)
            set_local_organization_context(conexao, organization_id)
            actor = UniversalReference(
                target_id=TypedId.new("actor"),
                organization_id=organization_id,
                contract_version=1,
            )
            identities = TransactionalRuleIdentityRepository(conexao)
            timeline = TransactionalRuleTimelineRepository(conexao)
            rules = TransactionalRuleRepository(conexao)
            adoptions = TransactionalRuleAdoptionRepository(conexao)
            identity = identities.get_by_organization_and_code(
                organization_id,
                ELIGIBILITY_RULE_CODE,
            )
            service = RuleGovernanceService(
                identities=identities,
                timeline=timeline,
                rules=rules,
                adoptions=adoptions,
            )
            if identity is None:
                identity = service.create_identity(
                    organization_id=organization_id,
                    code=ELIGIBILITY_RULE_CODE,
                    purpose="Elegibilidade farmacologica por mercado.",
                    scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    source_type=RuleSourceType.INTERNAL_POLICY,
                    actor=actor,
                    vertical="livestock",
                    description="Regra ficticia para validar matriz comercial.",
                )

            policy = PolicyService(TransactionalPolicyRepository(conexao)).create_draft(
                organization_id=organization_id,
                code=f"validacao-mercado-{uuid4().hex[:8]}",
                name="Policy de apoio para matriz de mercado",
                description="Registro ficticio criado pelo roteiro executavel.",
            )
            rule = service.publish_rule_version(
                organization_id=organization_id,
                rule_identity_id=identity.rule_identity_id,
                policy_id=policy.policy_id,
                name="Carencia farmacologica",
                actor=actor,
                severity=SeverityLevel.BLOCKING,
                normative_source="politica interna ficticia",
                required_evidence_types=("livestock.treatment_applied",),
                conditions=(
                    RuleCondition(
                        fact_type="livestock.withdrawal",
                        payload_key="in_withdrawal",
                        operator=ComparisonOperator.EQUALS,
                        expected_value=False,
                        description="Animal nao pode estar em periodo de carencia.",
                    ),
                ),
                justification="Destino comercial exige carencia cumprida.",
                corrective_action="Aguardar fim da carencia.",
            )
            for market in ("exportacao-china", "exportacao-estados-unidos"):
                existing = adoptions.get_active_by_identity_and_scope(
                    organization_id,
                    identity.rule_identity_id,
                    market,
                    ELIGIBILITY_RULE_ADOPTION_SCOPE,
                )
                if existing is not None:
                    continue
                service.adopt_rule_version(
                    organization_id=organization_id,
                    rule_identity_id=identity.rule_identity_id,
                    rule_version_id=rule.rule_id,
                    purpose=market,
                    scope=ELIGIBILITY_RULE_ADOPTION_SCOPE,
                    reason=f"Regra adotada para {market}.",
                    actor=actor,
                )
    finally:
        engine.dispose()


def _montar_roteiro(operador: Cliente, auditor: Cliente) -> Roteiro:
    ids: dict[str, str] = {}
    roteiro = Roteiro("ADR-0044 - Matriz de elegibilidade por mercado", diario=operador.diario)

    roteiro.passo(
        "1",
        "Operador encontra uma propriedade da Organization",
        lambda: operador.get("/v1/livestock/properties?limit=1"),
        200,
        conferir=lambda r: None if r["items"] else "nenhuma propriedade disponivel",
        guardar=lambda r: ids.update(property_id=str(r["items"][0]["property_id"])),
        porque="Nenhum identificador e copiado a mao; o roteiro descobre onde o animal nasce.",
    )
    roteiro.passo(
        "2",
        "Operador cria um animal para analisar",
        lambda: operador.post(
            "/v1/livestock/animals",
            {
                "birth_property_id": ids["property_id"],
                "sex": "MALE",
            },
        ),
        201,
        conferir=lambda r: None if r["animal_id"] else "sem animal_id",
        guardar=lambda r: ids.update(animal_id=str(r["animal_id"])),
        porque="A matriz responde sobre um animal real da Organization ativa.",
    )
    roteiro.passo(
        "3",
        "Operador executa a matriz de mercado",
        lambda: operador.post(
            f"/v1/livestock/animals/{ids['animal_id']}/eligibility/market-matrix",
            {},
        ),
        201,
        conferir=lambda r: (
            None
            if _matriz_tem_forma_esperada(r["markets"])
            else "matriz nao trouxe mercados, gaps e razoes esperados"
        ),
        porque=(
            "China e Estados Unidos foram preparados com regra adotada; Uniao "
            "Europeia deve aparecer como ausencia declarada."
        ),
    )
    roteiro.passo(
        "4",
        "Auditor nao executa matriz",
        lambda: auditor.post(
            f"/v1/livestock/animals/{ids['animal_id']}/eligibility/market-matrix",
            {},
        ),
        403,
        conferir=lambda r: (
            None
            if r["reason_code"] == "PERMISSAO_AUSENTE"
            else "negacao nao informou ausencia de permissao"
        ),
        porque="Consultar auditoria nao concede autoridade para emitir nova decisao.",
    )
    return roteiro


def _matriz_tem_forma_esperada(markets: list[dict[str, object]]) -> bool:
    by_market = {str(item["market"]): item for item in markets}
    expected = {
        "exportacao-uniao-europeia",
        "exportacao-china",
        "exportacao-estados-unidos",
    }
    if set(by_market) != expected:
        return False
    europe_gaps = by_market["exportacao-uniao-europeia"].get("gaps")
    europe_requirements = by_market["exportacao-uniao-europeia"].get("requirements")
    china_reasons = by_market["exportacao-china"].get("reasons")
    china_requirements = by_market["exportacao-china"].get("requirements")
    return (
        isinstance(europe_gaps, list)
        and bool(europe_gaps)
        and europe_gaps[0].get("code") == "REGRA_GOVERNADA_AUSENTE"
        and isinstance(europe_requirements, list)
        and [item.get("rule_code") for item in europe_requirements]
        == [ELIGIBILITY_RULE_CODE, TRACEABILITY_RULE_CODE]
        and [item.get("status") for item in europe_requirements] == ["AUSENTE", "AUSENTE"]
        and isinstance(china_reasons, list)
        and bool(china_reasons)
        and china_reasons[0].get("code") == "regra_atendida"
        and isinstance(china_requirements, list)
        and bool(china_requirements)
        and china_requirements[0].get("rule_code") == ELIGIBILITY_RULE_CODE
    )


def main() -> int:
    argumentos = argparse.ArgumentParser(description="Roteiro da ADR-0044.")
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
        raise SystemExit("Defina TITAN_DATABASE_URL para o roteiro preparar regras de mercado.")
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
    print(f"  Mercados     : {', '.join(profile.market for profile in DEFAULT_MARKET_PROFILES)}")
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
