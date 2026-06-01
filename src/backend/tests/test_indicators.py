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
    comp = ind.parkinson_volatility(bars, {"period": 3}, "1d")

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
    comp = ind.acceleration(bars, {"period": 1}, "1d")

    assert math.isclose(comp.latest, 1.0, rel_tol=1e-9)
    assert comp.reading.startswith("sustainable")


def test_acceleration_decelerating_is_exhausting():
    bars = [make_bar(c, c, c, c, 100) for c in (1, 5, 8, 10, 11)]  # accel -1
    comp = ind.acceleration(bars, {"period": 1}, "1d")

    assert comp.latest < 0
    assert comp.reading.startswith("exhausting")


def test_money_flow_all_buying_has_no_negative_flow():
    # Strictly rising typical price -> no negative flow -> ratio undefined, MFI 100.
    bars = [make_bar(i, i + 1, i, i + 0.5, 100) for i in range(1, 6)]
    comp = ind.money_flow_ratio(bars, {"period": 3}, "1d")

    assert comp.latest is None  # ratio undefined (no selling)
    assert math.isclose(comp.extra["mfi"], 100.0, rel_tol=1e-9)


def test_money_flow_known_ratio():
    bars = [
        make_bar(10, 10, 10, 10, 100),  # tp=10 baseline
        make_bar(11, 11, 11, 11, 100),  # tp=11 up -> +1100
        make_bar(10, 10, 10, 10, 110),  # tp=10 down -> -1100
    ]
    comp = ind.money_flow_ratio(bars, {"period": 2}, "1d")
    assert math.isclose(comp.latest, 1.0, rel_tol=1e-9)


def test_vwap_zscore_flat_prices_is_zero():
    bars = [make_bar(5, 5, 5, 5, 100) for _ in range(6)]
    comp = ind.vwap_zscore(bars, {"period": 3}, "1d")
    assert math.isclose(comp.latest, 0.0, abs_tol=1e-12)


# --------------------------------------------------------------------------- #
# New indicators: SMA / MACD / Bollinger
# --------------------------------------------------------------------------- #
def test_sma_known_mean_and_reading():
    bars = [make_bar(c, c, c, c, 100) for c in (10, 12, 14, 16, 18)]
    comp = ind.sma(bars, {"period": 3}, "1d")
    # Mean of the last 3 closes (14, 16, 18) = 16.
    assert math.isclose(comp.latest, 16.0, rel_tol=1e-9)
    # Last close (18) is above the SMA -> bullish.
    assert comp.reading.startswith("bullish")


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


def test_catalog_exposes_param_schema():
    macd = next(e for e in ind.available() if e["key"] == "macd")
    names = {p["name"] for p in macd["params"]}
    assert names == {"fast", "slow", "signal"}
    assert all({"name", "label", "default", "type"} <= p.keys() for p in macd["params"])


# --------------------------------------------------------------------------- #
# The full 20-indicator catalog
# --------------------------------------------------------------------------- #
ALL_KEYS = [
    "parkinson_volatility", "acceleration", "money_flow_ratio", "vwap_zscore",
    "sma", "macd", "bollinger", "ema", "rsi", "stochastic", "cci", "williams_r",
    "roc", "momentum", "atr", "adx", "parabolic_sar", "ichimoku", "keltner",
    "donchian", "obv", "vwap", "mfi", "cmf",
]


def test_all_indicators_registered():
    assert set(ALL_KEYS) <= set(ind.REGISTRY)


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
    results = ind.compute(bars, "1d", ALL_KEYS)
    assert set(results) == set(ALL_KEYS)
    for key, result in results.items():
        assert isinstance(result["reading"], str) and result["reading"]
        for name, points in result["series"].items():
            assert len(points) == len(bars), f"{key}.{name} not aligned"
            assert points[0]["timestamp"] == bars[0]["timestamp"]


def test_rsi_bounds_and_overbought_on_uptrend():
    # A strictly rising series has no losses -> RSI pins at 100 (overbought).
    bars = [make_bar(c, c, c, c, 100) for c in range(1, 40)]
    comp = ind.rsi(bars, {"period": 14}, "1d")
    assert math.isclose(comp.latest, 100.0, rel_tol=1e-9)
    assert comp.reading.startswith("overbought")


def test_donchian_breakout_to_new_high():
    bars = [make_bar(c, c + 1, c - 1, c, 100) for c in (5, 6, 7, 8, 20)]
    comp = ind.donchian(bars, {"period": 3}, "1d")
    # Last close (20) is the highest in the window -> bullish breakout.
    assert comp.reading.startswith("bullish")
    assert comp.lines["upper"][-1] >= comp.lines["lower"][-1]


def test_obv_accumulates_on_up_closes():
    bars = [make_bar(c, c, c, c, 100) for c in (10, 11, 12, 13)]
    comp = ind.obv(bars, {"period": 2}, "1d")
    # Every close is higher than the last, so OBV just sums volume.
    assert comp.lines["obv"] == [0.0, 100.0, 200.0, 300.0]
    assert comp.reading.startswith("accumulation")


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
        "sma",
        "macd",
        "bollinger",
    } <= keys
    # Catalog entries carry display metadata plus a param schema.
    assert all(
        {"key", "label", "description", "params"} <= e.keys() for e in ind.available()
    )


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
    results = ind.compute(
        bars,
        timeframe="1d",
        keys=["vwap_zscore"],
        params_by_key={"vwap_zscore": {"period": 3}},
    )

    assert set(results) == {"vwap_zscore"}
    result = results["vwap_zscore"]
    # Series is keyed and aligned 1:1 with the input bars.
    assert len(result["series"]["vwap_zscore"]) == len(bars)
    assert result["series"]["vwap_zscore"][0]["timestamp"] == bars[0]["timestamp"]
    assert {"key", "label", "description", "latest", "reading"} <= result.keys()
    # The resolved params used are echoed back.
    assert result["params"] == {"period": 3}
