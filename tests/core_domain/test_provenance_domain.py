"""Testes unitários do modelo de domínio para Proveniência (Passo 5.8)."""

import pytest

from packages.core_domain.provenance import (
    ProvenanceEdge,
    ProvenanceNode,
    ProvenanceNodeType,
    ProvenanceTrace,
)
from packages.shared_kernel import TypedId


def test_provenance_node_and_edge_invariants() -> None:
    src_id = TypedId.new("source")
    ev_id = TypedId.new("evidence")

    src_node = ProvenanceNode(
        node_id=src_id,
        node_type=ProvenanceNodeType.SOURCE,
        label="Source:DOCUMENT",
        metadata={"key": "val"},
    )
    assert src_node.node_id == src_id
    assert src_node.node_type == ProvenanceNodeType.SOURCE
    assert src_node.label == "Source:DOCUMENT"

    edge = ProvenanceEdge(
        source_node_id=src_id,
        target_node_id=ev_id,
        relation_type="ORIGINATED_FROM",
    )
    assert edge.source_node_id == src_id
    assert edge.target_node_id == ev_id
    assert edge.relation_type == "ORIGINATED_FROM"

    trace = ProvenanceTrace(root_id=src_id, nodes=(src_node,), edges=(edge,))
    assert trace.root_id == src_id
    assert len(trace.nodes) == 1
    assert len(trace.edges) == 1


def test_provenance_node_invalid_arguments() -> None:
    with pytest.raises(TypeError, match="node_id deve ser TypedId"):
        ProvenanceNode(
            node_id="invalid",  # type: ignore[arg-type]
            node_type=ProvenanceNodeType.SOURCE,
            label="Source:DOCUMENT",
        )

    with pytest.raises(ValueError, match="label deve ser uma string não vazia"):
        ProvenanceNode(
            node_id=TypedId.new("source"),
            node_type=ProvenanceNodeType.SOURCE,
            label="   ",
        )
