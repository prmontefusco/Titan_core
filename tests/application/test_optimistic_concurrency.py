import pytest

from packages.core_application import OptimisticConcurrencyConflict
from packages.core_infrastructure.persistence import EventAppendConflict


def test_persistence_conflict_implements_stable_application_contract() -> None:
    with pytest.raises(OptimisticConcurrencyConflict) as captured:
        raise EventAppendConflict

    assert captured.value.code == "VERSAO_DE_AGREGADO_CONFLITANTE"
    assert str(captured.value) == captured.value.code
