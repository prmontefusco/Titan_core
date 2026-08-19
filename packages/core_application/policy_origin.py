"""Classificação de origem homogênea de uma Policy (ADR-0064, BuyerPolicy Fase 1).

Uma Policy não carrega `RuleSourceType` próprio: a origem é sempre derivada das
`RuleIdentity`s das `Rule`s que ela publica (ADR-0043). Este módulo isola essa
derivação pura para ser reutilizada tanto na publicação de uma `RuleVersion`
(`RuleGovernanceService.publish_rule_version`) quanto na avaliação de uma Policy
(`apps/api/policy_governance.py`) — os dois pontos de verificação decididos no
design package da Fase 1.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from packages.core_domain.rule import Rule
from packages.core_domain.rule_governance import RuleIdentity, RuleSourceType
from packages.shared_kernel import OrganizationId


class RuleIdentityLookupPort(Protocol):
    def get_by_organization_and_code(
        self, organization_id: OrganizationId, code: str
    ) -> RuleIdentity | None: ...


@dataclass(frozen=True, slots=True)
class PolicyOrigin:
    """Resultado da derivação: origem homogênea encontrada, ou o motivo de não haver uma."""

    source_type: RuleSourceType | None
    homogeneous: bool
    missing_identity_codes: tuple[str, ...] = ()


def resolve_policy_origin(
    organization_id: OrganizationId,
    rules: Sequence[Rule],
    identities: RuleIdentityLookupPort,
) -> PolicyOrigin:
    """Deriva o `RuleSourceType` compartilhado pelas `Rule`s informadas.

    Vazio, `RuleIdentity` ausente para algum código ou mais de um `RuleSourceType`
    distinto produzem `homogeneous=False` — nunca uma origem inventada ou "a
    mais recente". Quem chama decide o efeito (recusar publicação, recusar
    avaliação, ou apresentar como não classificado como BuyerPolicy).
    """
    if not rules:
        return PolicyOrigin(source_type=None, homogeneous=False)

    source_types: set[RuleSourceType] = set()
    missing: list[str] = []
    for rule in rules:
        identity = identities.get_by_organization_and_code(organization_id, rule.code)
        if identity is None:
            missing.append(rule.code)
            continue
        source_types.add(identity.source_type)

    if missing or len(source_types) != 1:
        return PolicyOrigin(
            source_type=None,
            homogeneous=False,
            missing_identity_codes=tuple(sorted(set(missing))),
        )

    return PolicyOrigin(source_type=next(iter(source_types)), homogeneous=True)


def is_buyer_policy_origin(origin: PolicyOrigin) -> bool:
    """BuyerPolicy Fase 1 reconhece somente origem homogênea `INTERNAL_POLICY` (ADR-0064)."""
    return origin.homogeneous and origin.source_type is RuleSourceType.INTERNAL_POLICY
