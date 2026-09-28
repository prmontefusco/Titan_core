from pytest import MonkeyPatch

from apps.validacao.commercial_passport_api import (
    HttpResponse,
    _fail_closed_problem_contract,
    _pipeline_configuration_problem,
    _population_trace_projection,
    _sensitive_success_contract,
    _unauthenticated_boundary,
)
from apps.validacao.runner import Resposta


def _valid_pipeline_environment(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_CODE", "mercado-piloto")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME", "Mercado piloto")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_PURPOSE", "validacao-comercial")
    monkeypatch.setenv(
        "TITAN_COMMERCIAL_PASSPORT_POLICY_ID",
        "10000000-0000-4000-8000-000000000001",
    )
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION", "1")
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND", "MARKET")


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


def test_pipeline_configuration_validation_ignores_disabled_pipeline(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.delenv("TITAN_COMMERCIAL_PASSPORT_PIPELINE_ENABLED", raising=False)

    assert _pipeline_configuration_problem() is None


def test_pipeline_configuration_validation_accepts_complete_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    _valid_pipeline_environment(monkeypatch)

    assert _pipeline_configuration_problem() is None


def test_pipeline_configuration_validation_rejects_missing_required_metadata(
    monkeypatch: MonkeyPatch,
) -> None:
    _valid_pipeline_environment(monkeypatch)
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME", " ")

    assert _pipeline_configuration_problem() == (
        "pipeline habilitada, mas faltam metadados obrigatórios: "
        "TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_NAME"
    )


def test_pipeline_configuration_validation_rejects_invalid_policy_id(
    monkeypatch: MonkeyPatch,
) -> None:
    _valid_pipeline_environment(monkeypatch)
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_POLICY_ID", "nao-e-uuid")

    assert (
        _pipeline_configuration_problem()
        == "TITAN_COMMERCIAL_PASSPORT_POLICY_ID deve ser UUID não nulo de policy"
    )


def test_pipeline_configuration_validation_rejects_invalid_policy_version(
    monkeypatch: MonkeyPatch,
) -> None:
    _valid_pipeline_environment(monkeypatch)
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION", "0")

    assert (
        _pipeline_configuration_problem()
        == "TITAN_COMMERCIAL_PASSPORT_POLICY_VERSION deve ser inteiro >= 1"
    )


def test_pipeline_configuration_validation_rejects_invalid_opportunity_kind(
    monkeypatch: MonkeyPatch,
) -> None:
    _valid_pipeline_environment(monkeypatch)
    monkeypatch.setenv("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND", "TIPO_INEXISTENTE")

    problem = _pipeline_configuration_problem()

    assert problem is not None
    assert problem.startswith("TITAN_COMMERCIAL_PASSPORT_OPPORTUNITY_KIND inválido")
    assert "MARKET" in problem


def test_fail_closed_contract_accepts_problem_json_with_no_store() -> None:
    conferir = _fail_closed_problem_contract("COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO")
    resposta = Resposta(
        503,
        {"reason_code": "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"},
        {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "content-type": "application/problem+json; charset=utf-8",
        },
    )

    assert conferir(resposta) is None


def test_fail_closed_contract_accepts_method_not_allowed_problem() -> None:
    conferir = _fail_closed_problem_contract("METODO_NAO_PERMITIDO")
    resposta = Resposta(
        405,
        {"reason_code": "METODO_NAO_PERMITIDO"},
        {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "content-type": "application/problem+json; charset=utf-8",
        },
    )

    assert conferir(resposta) is None


def test_fail_closed_contract_rejects_missing_no_store() -> None:
    conferir = _fail_closed_problem_contract("COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO")
    resposta = Resposta(
        503,
        {"reason_code": "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"},
        {"content-type": "application/problem+json"},
    )

    assert conferir(resposta) == "resposta sensível não trouxe cache-control: no-store"


def test_fail_closed_contract_rejects_non_problem_json() -> None:
    conferir = _fail_closed_problem_contract("COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO")
    resposta = Resposta(
        503,
        {"reason_code": "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"},
        {
            "cache-control": "private, no-store",
            "pragma": "no-cache",
            "content-type": "application/json",
        },
    )

    assert conferir(resposta) == (
        "erro sensível não trouxe content-type application/problem+json (veio 'application/json')"
    )


def test_fail_closed_contract_rejects_missing_pragma_no_cache() -> None:
    conferir = _fail_closed_problem_contract("COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO")
    resposta = Resposta(
        503,
        {"reason_code": "COMMERCIAL_PASSPORT_PIPELINE_NAO_HABILITADO"},
        {
            "cache-control": "no-store",
            "content-type": "application/problem+json; charset=utf-8",
        },
    )

    assert conferir(resposta) == "resposta sensível não trouxe pragma: no-cache"


def test_sensitive_success_contract_requires_projection_and_no_store() -> None:
    conferir = _sensitive_success_contract(lambda _: None)
    resposta = Resposta(200, {}, {"cache-control": "max-age=0, no-store", "pragma": "no-cache"})

    assert conferir(resposta) is None


def test_sensitive_success_contract_rejects_missing_no_store() -> None:
    conferir = _sensitive_success_contract(lambda _: None)
    resposta = Resposta(200, {}, {"cache-control": "private", "pragma": "no-cache"})

    assert conferir(resposta) == "resposta sensível não trouxe cache-control: no-store"


def test_sensitive_success_contract_rejects_missing_pragma_no_cache() -> None:
    conferir = _sensitive_success_contract(lambda _: None)
    resposta = Resposta(200, {}, {"cache-control": "no-store"})

    assert conferir(resposta) == "resposta sensível não trouxe pragma: no-cache"


def test_unauthenticated_boundary_accepts_generic_error_body() -> None:
    response = HttpResponse(
        401,
        {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "content-type": "application/problem+json; charset=utf-8",
        },
        {"detail": "Not authenticated"},
    )

    assert _unauthenticated_boundary(response) is None


def test_unauthenticated_boundary_rejects_missing_no_store() -> None:
    response = HttpResponse(
        401,
        {"content-type": "application/problem+json"},
        {"detail": "Not authenticated"},
    )

    assert (
        _unauthenticated_boundary(response)
        == "resposta sem autenticação não trouxe cache-control: no-store"
    )


def test_unauthenticated_boundary_rejects_non_problem_json() -> None:
    response = HttpResponse(
        401,
        {
            "cache-control": "private, no-store",
            "pragma": "no-cache",
            "content-type": "application/json",
        },
        {"detail": "Not authenticated"},
    )

    assert _unauthenticated_boundary(response) == (
        "resposta sem autenticação não trouxe content-type application/problem+json "
        "(veio 'application/json')"
    )


def test_unauthenticated_boundary_rejects_missing_pragma_no_cache() -> None:
    response = HttpResponse(
        401,
        {
            "cache-control": "no-store",
            "content-type": "application/problem+json; charset=utf-8",
        },
        {"detail": "Not authenticated"},
    )

    assert (
        _unauthenticated_boundary(response)
        == "resposta sem autenticação não trouxe pragma: no-cache"
    )


def test_unauthenticated_boundary_rejects_commercial_passport_payload_key() -> None:
    response = HttpResponse(
        401,
        {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "content-type": "application/problem+json; charset=utf-8",
        },
        {"detail": "Not authenticated", "opportunities": []},
    )

    assert _unauthenticated_boundary(response) == (
        "resposta sem autenticação expôs campo proibido em body.opportunities"
    )


def test_unauthenticated_boundary_rejects_nested_population_trace_key() -> None:
    response = HttpResponse(
        401,
        {
            "cache-control": "no-store",
            "pragma": "no-cache",
            "content-type": "application/problem+json; charset=utf-8",
        },
        {"debug": [{"population_eligibility": {"total_count": 1}}]},
    )

    assert _unauthenticated_boundary(response) == (
        "resposta sem autenticação expôs campo proibido em body.debug[0].population_eligibility"
    )
