"""Tests for the Stage 3 indicator module (ported from srcV1 + v2 additions).

Golden values on hand-checkable series, parameter resolution, and an
all-indicators alignment smoke test. Standard library math only — no DB.
"""

import math

import pytest

from services.features import indicators as ind

TEN_KEYS = ["sma", "ema", "bollinger", "vwap", "rsi", "macd", "stochastic", "atr", "adx", "obv"]


def make_bar(o, h, low, c, v, ts="2026-05-15T00:00:00Z"):
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": v}


# --------------------------------------------------------------------------- #
# Golden values
# --------------------------------------------------------------------------- #
def test_sma_known_mean_and_reading():
    bars = [make_bar(c, c, c, c, 100) for c in (10, 12, 14, 16, 18)]
    comp = ind.sma(bars, {"period": 3}, "1d")
    # Mean of the last 3 closes (14, 16, 18) = 16.
    assert math.isclose(comp.latest, 16.0, rel_tol=1e-9)
    # Last close (18) is above the SMA -> bullish.
    assert comp.reading.startswith("bullish")
    # Warm-up: first period-1 values are None.
    assert comp.lines["sma"][:2] == [None, None]


def test_ema_seeds_with_simple_average_then_smooths():
    closes = [10.0, 12.0, 14.0, 16.0]
    bars = [make_bar(c, c, c, c, 100) for c in closes]
    comp = ind.ema(bars, {"period": 3}, "1d")
    series = comp.lines["ema"]
    assert series[:2] == [None, None]
    assert math.isclose(series[2], 12.0, rel_tol=1e-9)  # seed = mean(10,12,14)
    # Next value: 16*k + 12*(1-k), k = 2/(3+1) = 0.5 -> 14.
    assert math.isclose(series[3], 14.0, rel_tol=1e-9)


def test_macd_bullish_on_accelerating_series():
    # An accelerating uptrend keeps the MACD line climbing, so it stays above
    # its (lagging) signal EMA -> bullish. (A perfectly linear ramp is
    # degenerate: the EMAs converge and MACD collapses onto its signal line.)
    bars = [make_bar(c, c, c, c, 100) for c in (i * i for i in range(1, 60))]
    comp = ind.macd(bars, {"fast": 12, "slow": 26, "signal": 9}, "1d")
    assert comp.lines["macd"][-1] is not None
    assert comp.lines["signal"][-1] is not None
    assert comp.reading.startswith("bullish")


def test_bollinger_bands_ordering_and_flat_prices():
    # Flat prices -> zero std dev -> all three bands collapse onto the mean.
    flat = [make_bar(5, 5, 5, 5, 100) for _ in range(6)]
    comp = ind.bollinger(flat, {"period": 3, "std_mult": 2}, "1d")
    assert math.isclose(comp.lines["upper"][-1], 5.0, abs_tol=1e-12)
    assert math.isclose(comp.lines["lower"][-1], 5.0, abs_tol=1e-12)
    # With real variation the upper band sits above the lower band.
    varied = [make_bar(c, c, c, c, 100) for c in (1, 3, 2, 5, 4, 7)]
    comp = ind.bollinger(varied, {"period": 3, "std_mult": 2}, "1d")
    assert comp.lines["upper"][-1] > comp.lines["lower"][-1]


def test_vwap_equal_volume_is_mean_of_typical_prices():
    # Equal volumes make VWAP the plain mean of typical prices in the window.
    bars = [make_bar(c, c + 2, c - 2, c, 100) for c in (10.0, 20.0, 30.0)]
    comp = ind.vwap(bars, {"period": 3}, "1d")
    # Typical price = (H+L+C)/3 = close here (symmetric range) -> mean = 20.
    assert math.isclose(comp.latest, 20.0, rel_tol=1e-9)


def test_vwap_weights_by_volume():
    bars = [
        make_bar(10, 10, 10, 10, 100),  # tp=10, vol 100
        make_bar(20, 20, 20, 20, 300),  # tp=20, vol 300
    ]
    comp = ind.vwap(bars, {"period": 2}, "1d")
    # (10*100 + 20*300) / 400 = 17.5
    assert math.isclose(comp.latest, 17.5, rel_tol=1e-9)


def test_rsi_bounds_and_overbought_on_uptrend():
    # A strictly rising series has no losses -> RSI pins at 100 (overbought).
    bars = [make_bar(c, c, c, c, 100) for c in range(1, 40)]
    comp = ind.rsi(bars, {"period": 14}, "1d")
    assert math.isclose(comp.latest, 100.0, rel_tol=1e-9)
    assert comp.reading.startswith("overbought")


def test_stochastic_close_at_top_of_range_is_100():
    # Close == highest high of the window -> raw %K = 100 everywhere defined,
    # so smoothing leaves it at 100 and the reading is overbought.
    bars = [make_bar(c, c, c - 4, c, 100) for c in (10, 11, 12, 13, 14, 15)]
    comp = ind.stochastic(bars, {"k_period": 3, "d_period": 2, "smooth": 1}, "1d")
    assert math.isclose(comp.latest, 100.0, rel_tol=1e-9)
    assert comp.reading.startswith("overbought")


def test_atr_constant_range_equals_range():
    # Identical bars with H-L = 4 and no gaps -> every true range is 4, so the
    # Wilder average is exactly 4.
    bars = [make_bar(10, 12, 8, 10, 100) for _ in range(8)]
    comp = ind.atr(bars, {"period": 3}, "1d")
    assert math.isclose(comp.latest, 4.0, rel_tol=1e-9)


def test_adx_strong_uptrend_reads_bullish():
    # A persistent one-directional climb drives +DI >> -DI and ADX high.
    bars = [make_bar(100 + i, 101 + i, 99 + i, 100.5 + i, 100) for i in range(60)]
    comp = ind.adx(bars, {"period": 14}, "1d")
    assert comp.latest is not None and comp.latest > 25
    assert comp.reading.startswith("bullish")


def test_obv_accumulates_on_up_closes():
    bars = [make_bar(c, c, c, c, 100) for c in (10, 11, 12, 13)]
    comp = ind.obv(bars, {"period": 2}, "1d")
    # Every close is higher than the last, so OBV just sums volume.
    assert comp.lines["obv"] == [0.0, 100.0, 200.0, 300.0]
    assert comp.reading.startswith("accumulation")


# --------------------------------------------------------------------------- #
# Parameter resolution
# --------------------------------------------------------------------------- #
def test_resolve_params_defaults_and_clamping():
    spec = ind.REGISTRY["macd"]
    # Missing params fall back to declared defaults.
    assert ind._resolve_params(spec, None) == {"fast": 12, "slow": 26, "signal": 9}
    # Supplied values win; out-of-range values clamp to the min/max bounds.
    resolved = ind._resolve_params(spec, {"fast": 1, "slow": 9999, "signal": 5})
    assert resolved == {"fast": 2, "slow": 200, "signal": 5}


def test_resolve_params_coerces_types():
    spec = ind.REGISTRY["bollinger"]
    resolved = ind._resolve_params(spec, {"period": "30", "std_mult": "1.5"})
    assert resolved["period"] == 30 and isinstance(resolved["period"], int)
    assert resolved["std_mult"] == 1.5 and isinstance(resolved["std_mult"], float)


def test_catalog_exposes_param_schema_and_placement():
    entries = {e["key"]: e for e in ind.available()}
    macd = entries["macd"]
    assert {p["name"] for p in macd["params"]} == {"fast", "slow", "signal"}
    assert all({"name", "label", "default", "type"} <= p.keys() for p in macd["params"])
    # Placement drives where the chart draws each indicator.
    assert {entries[k]["placement"] for k in ("sma", "ema", "bollinger", "vwap")} == {"overlay"}
    assert {entries[k]["placement"] for k in ("rsi", "macd", "atr", "adx", "obv")} == {"pane"}


# --------------------------------------------------------------------------- #
# The 10-indicator catalog
# --------------------------------------------------------------------------- #
def test_the_ten_indicators_are_registered():
    assert list(ind.REGISTRY.keys()) == TEN_KEYS


def _ramp_bars(n=80):
    # A gently rising, noisy series with real high/low ranges and volume so
    # every indicator has something non-degenerate to chew on.
    bars = []
    for i in range(n):
        base = 100 + i * 0.5 + (3 if i % 5 == 0 else 0)
        bars.append(make_bar(base, base + 1.5, base - 1.2, base + 0.3, 1000 + i * 10))
    return bars


def test_every_indicator_computes_and_aligns():
    # Smoke-test the whole catalog end-to-end through compute(): each returns a
    # reading and series aligned 1:1 with the input bars.
    bars = _ramp_bars()
    results = ind.compute(bars, "1d", TEN_KEYS)
    assert set(results) == set(TEN_KEYS)
    for key, result in results.items():
        assert isinstance(result["reading"], str) and result["reading"]
        for name, points in result["series"].items():
            assert len(points) == len(bars), f"{key}.{name} not aligned"
            assert points[0]["timestamp"] == bars[0]["timestamp"]


# --------------------------------------------------------------------------- #
# Registry / selection
# --------------------------------------------------------------------------- #
def test_resolve_keys_all_and_subset():
    assert ind.resolve_keys(None) == TEN_KEYS
    assert ind.resolve_keys([]) == TEN_KEYS
    assert ind.resolve_keys(["vwap", "rsi"]) == ["vwap", "rsi"]
    # De-dupes while preserving order.
    assert ind.resolve_keys(["rsi", "rsi"]) == ["rsi"]


def test_resolve_keys_rejects_unknown():
    with pytest.raises(ValueError):
        ind.resolve_keys(["not_a_real_indicator"])


def test_compute_returns_only_requested():
    bars = _ramp_bars(30)
    results = ind.compute(bars, "1d", ["rsi"], params_by_key={"rsi": {"period": 5}})

    assert set(results) == {"rsi"}
    result = results["rsi"]
    # Series is keyed and aligned 1:1 with the input bars.
    assert len(result["series"]["rsi"]) == len(bars)
    assert {"key", "label", "description", "placement", "latest", "reading"} <= result.keys()
    # The resolved params used are echoed back.
    assert result["params"] == {"period": 5}
