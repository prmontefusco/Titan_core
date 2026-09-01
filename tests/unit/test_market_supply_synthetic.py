from apps.validacao.market_supply_synthetic import build_synthetic_supply_intelligence_report


def test_synthetic_market_supply_report_preserves_f0_guardrails() -> None:
    report = build_synthetic_supply_intelligence_report()

    assert report["report_type"] == "SupplyIntelligenceReport"
    assert report["status"] == "SYNTHETIC_PROTOTYPE_NOT_FOR_PRODUCTION"
    assert report["commercial_demand"]["purpose"] == "MARKET_SUPPLY_AGGREGATE_ASSESSMENT"
    assert "candidate_membership" in report["explicitly_not_disclosed"]
    assert "no production API" in report["limitations"]
    assert "no persistence" in report["limitations"]
    assert "no real cross-tenant access" in report["limitations"]


def test_synthetic_market_supply_counts_are_internally_consistent() -> None:
    report = build_synthetic_supply_intelligence_report()

    population = report["candidate_population_snapshot"]
    readiness_counts = report["market_readiness_summary"]
    analysis = report["supply_demand_analysis"]

    assert sum(readiness_counts.values()) == population["included_count"]
    assert population["excluded_count"] == 1
    assert analysis["estimated_capacity"] == (
        analysis["ready_now"] + analysis["potential_in_window"]
    )
    assert analysis["estimated_shortage"] == max(
        analysis["requested_quantity"] - analysis["estimated_capacity"],
        0,
    )


def test_synthetic_market_supply_temporal_and_policy_context_is_explicit() -> None:
    report = build_synthetic_supply_intelligence_report()
    population = report["candidate_population_snapshot"]
    demand = report["commercial_demand"]

    assert report["generated_at"]
    assert population["reference_time"]
    assert population["knowledge_cutoff"]
    assert demand["policy_code"] == "SYNTHETIC_MARKET_POLICY_A"
    assert demand["policy_version"] == "v0.synthetic"


def test_synthetic_market_supply_forecast_is_limited_and_non_decisional() -> None:
    report = build_synthetic_supply_intelligence_report()
    forecast = report["supply_forecast"]

    assert forecast["included"] is True
    assert forecast["forecast_type"] == "deterministic_synthetic_scenario"
    assert "not a Decision" in forecast["limitations"]
    assert "not future eligibility" in forecast["limitations"]
    assert "not a guarantee of availability" in forecast["limitations"]
