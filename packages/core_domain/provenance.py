"""Estruturas imutáveis do modelo de domínio para Linhagem e Proveniência (ADR-0038/Passo 5.8)."""

from dataclasses import dataclass, field
from enum import Enum

from packages.shared_kernel import TypedId


class ProvenanceNodeType(Enum):
    SOURCE = "source"
    EVIDENCE = "evidence"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    node_id: TypedId
    node_type: ProvenanceNodeType
    label: str
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, TypedId):
            raise TypeError("node_id deve ser TypedId.")
        if not isinstance(self.node_type, ProvenanceNodeType):
            raise TypeError("node_type deve ser ProvenanceNodeType.")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("label deve ser uma string não vazia.")


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    source_node_id: TypedId
    target_node_id: TypedId
    relation_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_node_id, TypedId):
            raise TypeError("source_node_id deve ser TypedId.")
        if not isinstance(self.target_node_id, TypedId):
            raise TypeError("target_node_id deve ser TypedId.")
        if not isinstance(self.relation_type, str) or not self.relation_type.strip():
            raise ValueError("relation_type deve ser uma string não vazia.")


@dataclass(frozen=True, slots=True)
class ProvenanceTrace:
    root_id: TypedId
    nodes: tuple[ProvenanceNode, ...]
    edges: tuple[ProvenanceEdge, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.root_id, TypedId):
            raise TypeError("root_id deve ser TypedId.")
        if not isinstance(self.nodes, tuple):
            raise TypeError("nodes deve ser uma tupla.")
        if not isinstance(self.edges, tuple):
            raise TypeError("edges deve ser uma tupla.")
