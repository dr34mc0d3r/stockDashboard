import math

import pytest

from backend.services import indicators as ind


def make_bar(o, h, l, c, v, ts="2026-05-15T00:00:00Z"):
    return {
        "timestamp": ts,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "volume": v,
    }


def test_parkinson_constant_range():
    # Every bar has ln(H/L) == 1, so each squared term is 1 and the rolling
    # estimate collapses to sqrt(1 / (4*ln2)).
    bars = [make_bar(1, math.e, 1.0, 2.0, 100) for _ in range(5)]
    comp = ind.parkinson_volatility(bars, period=3, timeframe="1d")

    expected = math.sqrt(1.0 / (4.0 * math.log(2.0)))
    assert math.isclose(comp.latest, expected, rel_tol=1e-9)
    # First two bars are warm-up.
    series = comp.lines["parkinson_volatility"]
    assert series[0] is None and series[1] is None
    # Annualized = per-bar * sqrt(252) for the daily timeframe.
    assert math.isclose(comp.extra["annualized"], expected * math.sqrt(252), rel_tol=1e-9)


def test_acceleration_constant_second_difference():
    # closes increase by 1,2,3,4 -> velocity (period=1) is 1,2,3,4 -> accel is 1.
    bars = [make_bar(c, c, c, c, 100) for c in (1, 2, 4, 7, 11)]
    comp = ind.acceleration(bars, period=1)

    assert math.isclose(comp.latest, 1.0, rel_tol=1e-9)
    assert comp.reading.startswith("sustainable")


def test_acceleration_decelerating_is_exhausting():
    bars = [make_bar(c, c, c, c, 100) for c in (1, 5, 8, 10, 11)]  # accel -1
    comp = ind.acceleration(bars, period=1)

    assert comp.latest < 0
    assert comp.reading.startswith("exhausting")


def test_money_flow_all_buying_has_no_negative_flow():
    # Strictly rising typical price -> no negative flow -> ratio undefined, MFI 100.
    bars = [make_bar(i, i + 1, i, i + 0.5, 100) for i in range(1, 6)]
    comp = ind.money_flow_ratio(bars, period=3)

    assert comp.latest is None  # ratio undefined (no selling)
    assert math.isclose(comp.extra["mfi"], 100.0, rel_tol=1e-9)


def test_money_flow_known_ratio():
    bars = [
        make_bar(10, 10, 10, 10, 100),  # tp=10 baseline
        make_bar(11, 11, 11, 11, 100),  # tp=11 up -> +1100
        make_bar(10, 10, 10, 10, 110),  # tp=10 down -> -1100
    ]
    comp = ind.money_flow_ratio(bars, period=2)
    assert math.isclose(comp.latest, 1.0, rel_tol=1e-9)


def test_vwap_zscore_flat_prices_is_zero():
    bars = [make_bar(5, 5, 5, 5, 100) for _ in range(6)]
    comp = ind.vwap_zscore(bars, period=3)
    assert math.isclose(comp.latest, 0.0, abs_tol=1e-12)


# --------------------------------------------------------------------------- #
# Registry / selection
# --------------------------------------------------------------------------- #
def test_catalog_lists_all_registered():
    keys = {entry["key"] for entry in ind.available()}
    assert {
        "parkinson_volatility",
        "acceleration",
        "money_flow_ratio",
        "vwap_zscore",
    } <= keys
    # Catalog entries carry display metadata.
    assert all({"key", "label", "description"} <= e.keys() for e in ind.available())


def test_resolve_keys_all_and_subset():
    assert ind.resolve_keys("all") == list(ind.REGISTRY.keys())
    assert ind.resolve_keys("") == list(ind.REGISTRY.keys())
    assert ind.resolve_keys("vwap_zscore,acceleration") == [
        "vwap_zscore",
        "acceleration",
    ]
    # De-dupes while preserving order.
    assert ind.resolve_keys("acceleration,acceleration") == ["acceleration"]


def test_resolve_keys_rejects_unknown():
    with pytest.raises(ValueError):
        ind.resolve_keys("not_a_real_indicator")


def test_compute_returns_only_requested():
    bars = [make_bar(i, i + 1, i - 0.5, i + 0.2, 100 + i) for i in range(2, 12)]
    results = ind.compute(bars, period=3, timeframe="1d", keys=["vwap_zscore"])

    assert set(results) == {"vwap_zscore"}
    result = results["vwap_zscore"]
    # Series is keyed and aligned 1:1 with the input bars.
    assert len(result["series"]["vwap_zscore"]) == len(bars)
    assert result["series"]["vwap_zscore"][0]["timestamp"] == bars[0]["timestamp"]
    assert {"key", "label", "description", "latest", "reading"} <= result.keys()
