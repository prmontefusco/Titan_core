"""Caso de uso de Rastreamento de Linhagem e Proveniência (ADR-0038/Passo 5.8)."""

from dataclasses import dataclass
from typing import Any, Protocol

from packages.core_domain.evidence import Evidence
from packages.core_domain.provenance import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceTrace,
)
from packages.shared_kernel import TypedId


class EvidenceLookupPort(Protocol):
    def get_by_id(self, evidence_id: TypedId) -> Evidence | None: ...

    def list_by_source(self, source_id: TypedId) -> list[Evidence]: ...


class EventLookupItemPort(Protocol):
    event_id: TypedId
    event_type: str
    source_reference: Any


class EventLookupPort(Protocol):
    def get_by_id(self, event_id: TypedId) -> Any | None: ...

    def list_by_source_id(self, source_id: TypedId) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class ProvenanceService:
    evidence_repository: EvidenceLookupPort
    event_repository: EventLookupPort

    def trace_from_event(self, event_id: TypedId) -> ProvenanceTrace:
        event = self.event_repository.get_by_id(event_id)
        if event is None:
            raise KeyError(f"Evento de domínio {event_id.value} não encontrado.")

        nodes: list[ProvenanceNode] = []
        edges: list[ProvenanceEdge] = []

        event_node = ProvenanceNode(
            node_id=event.event_id,
            node_type=ProvenanceNodeType.EVENT,
            label=f"DomainEvent:{event.event_type}",
            metadata={"event_type": event.event_type},
        )
        nodes.append(event_node)

        source_id = event.source_reference.target_id
        evidences = self.evidence_repository.list_by_source(source_id)

        if evidences:
            for evidence in evidences:
                ev_node = ProvenanceNode(
                    node_id=evidence.evidence_id,
                    node_type=ProvenanceNodeType.EVIDENCE,
                    label=f"Evidence:{evidence.source.source_type.value}",
                    metadata={"source_type": evidence.source.source_type.value},
                )
                nodes.append(ev_node)
                edges.append(
                    ProvenanceEdge(
                        source_node_id=evidence.evidence_id,
                        target_node_id=event.event_id,
                        relation_type="FUNDAMENTED_BY",
                    )
                )

                source_node = ProvenanceNode(
                    node_id=evidence.source.source_id,
                    node_type=ProvenanceNodeType.SOURCE,
                    label=f"Source:{evidence.source.source_type.value}",
                    metadata={"source_type": evidence.source.source_type.value},
                )
                nodes.append(source_node)
                edges.append(
                    ProvenanceEdge(
                        source_node_id=evidence.source.source_id,
                        target_node_id=evidence.evidence_id,
                        relation_type="ORIGINATED_FROM",
                    )
                )
        else:
            source_node = ProvenanceNode(
                node_id=source_id,
                node_type=ProvenanceNodeType.SOURCE,
                label=f"Source:{source_id.entity_type}",
                metadata={"source_type": source_id.entity_type},
            )
            nodes.append(source_node)
            edges.append(
                ProvenanceEdge(
                    source_node_id=source_id,
                    target_node_id=event.event_id,
                    relation_type="ORIGINATED_FROM",
                )
            )

        return ProvenanceTrace(root_id=event.event_id, nodes=tuple(nodes), edges=tuple(edges))

    def trace_from_evidence(self, evidence_id: TypedId) -> ProvenanceTrace:
        evidence = self.evidence_repository.get_by_id(evidence_id)
        if evidence is None:
            raise KeyError(f"Evidência {evidence_id.value} não encontrada.")

        nodes: list[ProvenanceNode] = []
        edges: list[ProvenanceEdge] = []

        ev_node = ProvenanceNode(
            node_id=evidence.evidence_id,
            node_type=ProvenanceNodeType.EVIDENCE,
            label=f"Evidence:{evidence.source.source_type.value}",
            metadata={"source_type": evidence.source.source_type.value},
        )
        nodes.append(ev_node)

        source_node = ProvenanceNode(
            node_id=evidence.source.source_id,
            node_type=ProvenanceNodeType.SOURCE,
            label=f"Source:{evidence.source.source_type.value}",
            metadata={"source_type": evidence.source.source_type.value},
        )
        nodes.append(source_node)
        edges.append(
            ProvenanceEdge(
                source_node_id=evidence.source.source_id,
                target_node_id=evidence.evidence_id,
                relation_type="ORIGINATED_FROM",
            )
        )

        events = self.event_repository.list_by_source_id(evidence.source.source_id)
        for ev in events:
            ev_event_node = ProvenanceNode(
                node_id=ev.event_id,
                node_type=ProvenanceNodeType.EVENT,
                label=f"DomainEvent:{ev.event_type}",
                metadata={"event_type": ev.event_type},
            )
            nodes.append(ev_event_node)
            edges.append(
                ProvenanceEdge(
                    source_node_id=evidence.evidence_id,
                    target_node_id=ev.event_id,
                    relation_type="FUNDAMENTED_BY",
                )
            )

        return ProvenanceTrace(root_id=evidence.evidence_id, nodes=tuple(nodes), edges=tuple(edges))

    def trace_from_source(self, source_id: TypedId) -> ProvenanceTrace:
        evidences = self.evidence_repository.list_by_source(source_id)
        events = self.event_repository.list_by_source_id(source_id)

        if not evidences and not events:
            raise KeyError(f"Nenhum registro encontrado para a fonte {source_id.value}.")

        nodes: list[ProvenanceNode] = []
        edges: list[ProvenanceEdge] = []

        source_label = (
            f"Source:{evidences[0].source.source_type.value}"
            if evidences
            else f"Source:{source_id.entity_type}"
        )
        source_node = ProvenanceNode(
            node_id=source_id,
            node_type=ProvenanceNodeType.SOURCE,
            label=source_label,
            metadata={"source_id": str(source_id.value)},
        )
        nodes.append(source_node)

        for evidence in evidences:
            ev_node = ProvenanceNode(
                node_id=evidence.evidence_id,
                node_type=ProvenanceNodeType.EVIDENCE,
                label=f"Evidence:{evidence.source.source_type.value}",
                metadata={"source_type": evidence.source.source_type.value},
            )
            nodes.append(ev_node)
            edges.append(
                ProvenanceEdge(
                    source_node_id=source_id,
                    target_node_id=evidence.evidence_id,
                    relation_type="ORIGINATED_FROM",
                )
            )

        for ev in events:
            ev_event_node = ProvenanceNode(
                node_id=ev.event_id,
                node_type=ProvenanceNodeType.EVENT,
                label=f"DomainEvent:{ev.event_type}",
                metadata={"event_type": ev.event_type},
            )
            nodes.append(ev_event_node)
            parent_id = evidences[0].evidence_id if evidences else source_id
            rel_type = "FUNDAMENTED_BY" if evidences else "ORIGINATED_FROM"
            edges.append(
                ProvenanceEdge(
                    source_node_id=parent_id,
                    target_node_id=ev.event_id,
                    relation_type=rel_type,
                )
            )

        return ProvenanceTrace(root_id=source_id, nodes=tuple(nodes), edges=tuple(edges))
