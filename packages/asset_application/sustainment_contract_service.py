"""Caso de uso do agregado `SLIContract` — Titan Asset (A4, módulo `sustainment`).

`IssueContractVersion` e `AmendContract` (`09_COMMAND_MODEL.md`) são a **mesma**
operação de domínio (`issue_contract_version` aqui, chamando
`SLIContract.issue_version`) — a diferença entre as duas é só permissão
(`SUSTAINMENT_CONTRACT.ISSUE_VERSION` vs `.AMEND`, checadas em A5) e se
`version.amendment_ref` vem preenchido pelo chamador; o domínio não distingue
(mesmo padrão de `configuration_service.publish_baseline` unificando
`PublishConfigurationBaseline`/`SupersedeConfigurationRevision`).

**`ResolveEntitlement`/`AuthorizeEntitlementException` (I-SLI-4/5) não estão
aqui** — pedem `Evaluation`→`Decision` do Core e, no segundo caso, coordenação
com `WorkOrder` (T7). Ficam para o próprio incremento de entitlement, depois
de `work_order_service.py` existir o suficiente para a coordenação fazer
sentido (constituição §38: sem consumidor real, é design antecipado).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from packages.asset_application.event_recorder import AssetEventRecorder, AssetOperationContext
from packages.asset_domain.events import (
    SUSTAINMENT_CONTRACT_REGISTERED,
    SUSTAINMENT_CONTRACT_VERSION_ISSUED,
    sustainment_contract_registered_payload,
    sustainment_contract_version_issued_payload,
)
from packages.asset_domain.sustainment_contract import ContractVersion, SLIContract
from packages.shared_kernel import TypedId


class SLIContractNaoEncontrado(KeyError):
    """`contract_id` não corresponde a nenhum `SLIContract` desta Organization."""


class SLIContractRepositoryPort(Protocol):
    def save(self, contract: SLIContract) -> None: ...

    def update(self, contract: SLIContract) -> None: ...

    def get_by_id(self, contract_id: TypedId) -> SLIContract | None: ...


def _coverage_summary(version: ContractVersion) -> str:
    if not version.coverage_lines:
        return "sem cobertura declarada"
    return "; ".join(f"{line.scope.value}={line.scope_value}" for line in version.coverage_lines)


@dataclass(frozen=True, slots=True)
class SLIContractService:
    repository: SLIContractRepositoryPort
    recorder: AssetEventRecorder

    def _require(self, contract_id: TypedId) -> SLIContract:
        contract = self.repository.get_by_id(contract_id)
        if contract is None:
            raise SLIContractNaoEncontrado(f"SLIContract '{contract_id.value}' não encontrado.")
        return contract

    def register_contract(
        self,
        context: AssetOperationContext,
        *,
        customer_ref: TypedId,
        occurred_at: datetime,
    ) -> SLIContract:
        contract = SLIContract(
            contract_id=TypedId.new("sli_contract"),
            organization_id=context.organization_id,
            customer_ref=customer_ref,
        )
        self.repository.save(contract)
        self.recorder.record(
            context=context,
            aggregate_id=contract.contract_id,
            event_type=SUSTAINMENT_CONTRACT_REGISTERED,
            payload=sustainment_contract_registered_payload(
                contract_id=contract.contract_id, customer_ref=customer_ref
            ),
            occurred_at=occurred_at,
        )
        return contract

    def issue_contract_version(
        self,
        context: AssetOperationContext,
        contract_id: TypedId,
        *,
        version: ContractVersion,
        occurred_at: datetime,
    ) -> SLIContract:
        contract = self._require(contract_id)
        updated = contract.issue_version(version)
        self.repository.update(updated)
        self.recorder.record(
            context=context,
            aggregate_id=updated.contract_id,
            event_type=SUSTAINMENT_CONTRACT_VERSION_ISSUED,
            payload=sustainment_contract_version_issued_payload(
                contract_id=updated.contract_id,
                version_no=version.version_no,
                valid_from=version.effective.valid_from,
                coverage_summary=_coverage_summary(version),
                amendment_ref=version.amendment_ref,
            ),
            occurred_at=occurred_at,
        )
        return updated

    def get_contract(self, contract_id: TypedId) -> SLIContract | None:
        return self.repository.get_by_id(contract_id)
