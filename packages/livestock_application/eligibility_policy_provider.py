"""Política e regra de elegibilidade persistidas (Passo 10.4b).

Até aqui a política e a regra eram construídas em memória a cada avaliação. Isso
passava nos testes unitários — repositórios falsos não impõem integridade — e
falhava contra o PostgreSQL: `evaluations` tem chave estrangeira para `policies`,
e uma avaliação não pode referenciar política que não existe.

O defeito era mais fundo que a chave estrangeira. Política construída em memória
não tem existência própria: não pode ser consultada, comparada com a de ontem,
nem citada por um dossiê emitido no ano passado. Uma decisão só é reproduzível se
a norma sob a qual foi tomada estiver registrada.

Este provedor grava a política e a regra na primeira vez e **reusa** nas
seguintes, procurando por código e versão. É o passo mínimo na direção da nota de
rumo NR-5: quando a autoria passar ao administrador, o que muda é quem escreve a
política — a leitura pela versão vigente já estará aqui.
"""

from dataclasses import dataclass
from typing import Protocol

from packages.core_domain.policy import Policy
from packages.core_domain.rule import Rule
from packages.livestock_application.eligibility import (
    ELIGIBILITY_POLICY_CODE,
    ELIGIBILITY_RULE_CODE,
    LOT_ELIGIBILITY_RULE_CODE,
    build_eligibility_policy,
    build_eligibility_rule,
    build_lot_eligibility_rule,
)
from packages.shared_kernel import OrganizationId, TypedId

POLICY_VERSION = 1


class PolicyRepositoryPort(Protocol):
    def save(self, policy: Policy) -> None: ...

    def get_by_code_and_version(
        self, organization_id: OrganizationId, code: str, version: int
    ) -> Policy | None: ...


class RuleRepositoryPort(Protocol):
    def save(self, rule: Rule) -> None: ...

    def list_by_policy(self, organization_id: OrganizationId, policy_id: TypedId) -> list[Rule]: ...


@dataclass(frozen=True, slots=True)
class EligibilityPolicyProvider:
    """Devolve a política e as regras vigentes, gravando-as se ainda não existirem."""

    policy_repository: PolicyRepositoryPort
    rule_repository: RuleRepositoryPort

    def current(self, organization_id: OrganizationId) -> tuple[Policy, Rule]:
        policy = self.policy_repository.get_by_code_and_version(
            organization_id, ELIGIBILITY_POLICY_CODE, POLICY_VERSION
        )
        if policy is None:
            policy = build_eligibility_policy(organization_id)
            self.policy_repository.save(policy)
            # As duas regras nascem juntas: a de animal e a de lote pertencem à
            # mesma política publicada, e gravar só uma deixaria a outra órfã.
            animal_rule = build_eligibility_rule(policy.policy_id, organization_id)
            self.rule_repository.save(animal_rule)
            self.rule_repository.save(build_lot_eligibility_rule(policy.policy_id, organization_id))
            return policy, animal_rule

        regras = self.rule_repository.list_by_policy(organization_id, policy.policy_id)
        vigente = next((regra for regra in regras if regra.code == ELIGIBILITY_RULE_CODE), None)
        if vigente is None:
            # Política sem a regra que a sustenta é estado inconsistente, e
            # avaliar assim produziria decisão sem norma.
            raise RuntimeError(
                f"A política '{ELIGIBILITY_POLICY_CODE}' existe sem a regra de carência."
            )
        return policy, vigente

    def current_lot_rule(self, organization_id: OrganizationId, policy: Policy) -> Rule:
        """Regra de lote (`rule-carencia-lote`) da mesma política vigente.

        `evaluate_lot` exige essa regra à parte da regra de animal — as duas
        nascem juntas em `.current()`, mas cada avaliação (por animal ou por
        lote) só precisa da que lhe cabe.
        """
        regras = self.rule_repository.list_by_policy(organization_id, policy.policy_id)
        vigente = next((regra for regra in regras if regra.code == LOT_ELIGIBILITY_RULE_CODE), None)
        if vigente is None:
            raise RuntimeError(
                f"A política '{ELIGIBILITY_POLICY_CODE}' existe sem a regra de carência de lote."
            )
        return vigente
