from apps.validacao.commercial_passport_api import _population_trace_projection


def _population_trace() -> dict[str, object]:
    return {
        "total_count": 3,
        "counts_by_status": {
            "READY": 1,
            "NOT_READY": 0,
            "CONDITIONED": 0,
            "INDETERMINATE": 0,
            "REASSESSMENT_REQUIRED": 0,
            "NOT_EVALUATED": 2,
        },
        "blocker_count": 0,
        "population_snapshot_digest": "population:sha256:abc",
        "selection_criteria_digest": "criteria:sha256:def",
        "commercial_window": {
            "start": "2026-09-11T00:00:00Z",
            "end": "2026-09-18T00:00:00Z",
        },
    }


def test_population_trace_validation_accepts_aggregate_trace_without_individual_ids() -> None:
    assert _population_trace_projection(_population_trace()) is None


def test_population_trace_validation_rejects_empty_digest() -> None:
    trace = _population_trace()
    trace["population_snapshot_digest"] = " "

    assert (
        _population_trace_projection(trace)
        == "resumo populacional não trouxe population_snapshot_digest textual e não vazio"
    )


def test_population_trace_validation_rejects_empty_commercial_window_boundary() -> None:
    trace = _population_trace()
    trace["commercial_window"] = {
        "start": "2026-09-11T00:00:00Z",
        "end": "",
    }

    assert (
        _population_trace_projection(trace)
        == "commercial_window.end não trouxe timestamp textual e não vazio"
    )


def test_population_trace_validation_rejects_individual_animal_ids() -> None:
    trace = _population_trace()
    trace["debug"] = {"animal_ids": ["animal-1"]}

    assert _population_trace_projection(trace) == (
        "resumo populacional expôs identificador individual proibido "
        "em population_eligibility.debug.animal_ids"
    )
