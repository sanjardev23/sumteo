from sumteo.events.models import Severity


def test_severity_rank_orders_escalation():
    assert Severity.INFO.rank < Severity.WARNING.rank < Severity.CRITICAL.rank

# TODO(Day 1): tests/test_zones.py — Polygon.contains
# TODO(Day 2): RuleEngine — flicker doesn't fire, cooldown blocks repeats, escalation fires
