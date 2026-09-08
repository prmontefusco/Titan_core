from packages.livestock_application.authorization import (
    AUDITOR,
    FRIGORIFICO,
    LIVESTOCK_PERMISSIONS,
    MARKET_OPTION_EXPLAIN,
    MARKET_SUPPLY_AGGREGATE_ASSESS,
    OPERADOR_PECUARIO,
    ROLE_PERMISSIONS,
)


def test_market_supply_aggregate_permission_is_catalogued_for_f3_5() -> None:
    assert MARKET_SUPPLY_AGGREGATE_ASSESS == "MARKET_SUPPLY.AGGREGATE_ASSESS"
    assert MARKET_SUPPLY_AGGREGATE_ASSESS in LIVESTOCK_PERMISSIONS


def test_market_supply_aggregate_permission_is_not_granted_by_default_roles() -> None:
    assert MARKET_SUPPLY_AGGREGATE_ASSESS not in ROLE_PERMISSIONS[OPERADOR_PECUARIO]
    assert MARKET_SUPPLY_AGGREGATE_ASSESS not in ROLE_PERMISSIONS[AUDITOR]
    assert MARKET_SUPPLY_AGGREGATE_ASSESS not in ROLE_PERMISSIONS[FRIGORIFICO]


def test_market_option_explain_permission_is_catalogued() -> None:
    assert MARKET_OPTION_EXPLAIN == "MARKET_OPTION.EXPLAIN"
    assert MARKET_OPTION_EXPLAIN in LIVESTOCK_PERMISSIONS


def test_market_option_explain_permission_is_not_granted_by_default_roles() -> None:
    assert MARKET_OPTION_EXPLAIN not in ROLE_PERMISSIONS[OPERADOR_PECUARIO]
    assert MARKET_OPTION_EXPLAIN not in ROLE_PERMISSIONS[AUDITOR]
    assert MARKET_OPTION_EXPLAIN not in ROLE_PERMISSIONS[FRIGORIFICO]
