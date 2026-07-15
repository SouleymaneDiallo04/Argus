from __future__ import annotations

from app.domain.types import Zone, ComplianceResult
from app.domain.compliance import evaluate


def test_compliant_when_all_required_present():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet", "safety-vest"}))
    res = evaluate(1, {"helmet", "safety-vest", "gloves"}, zone)
    assert res.compliant is True
    assert res.missing == frozenset()
    assert res.zone == "A"
    assert res.required == frozenset({"helmet", "safety-vest"})


def test_non_compliant_lists_missing():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet", "safety-vest"}))
    res = evaluate(1, {"helmet"}, zone)
    assert res.compliant is False
    assert res.missing == frozenset({"safety-vest"})


def test_no_zone_means_compliant_with_no_requirements():
    res = evaluate(7, set(), None)
    assert res.compliant is True
    assert res.zone is None
    assert res.required == frozenset()
    assert res.missing == frozenset()


def test_result_type_is_compliance_result():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet"}))
    res = evaluate(1, set(), zone)
    assert isinstance(res, ComplianceResult)
    assert res.present == frozenset()
