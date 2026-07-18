from __future__ import annotations

import pytest

from backtester.costs import (
    COST_MODELS,
    BaseCostModel,
    FlatPerTrade,
    PctOfValue,
    VolumeSlippage,
    get_cost_model,
)


def test_flat_per_trade_returns_commission_and_zero_slippage() -> None:
    model = FlatPerTrade(commission=2.5)
    commission, slippage = model.apply(fill_price=100.0, qty=10)
    assert commission == pytest.approx(2.5)
    assert slippage == pytest.approx(0.0)


def test_flat_per_trade_default_commission() -> None:
    model = FlatPerTrade()
    assert model.apply(50.0, 5) == (1.0, 0.0)


def test_flat_per_trade_negative_commission_rejected() -> None:
    with pytest.raises(ValueError):
        FlatPerTrade(commission=-1.0)


def test_pct_of_value_matches_formula() -> None:
    model = PctOfValue(rate=0.001)
    price, qty = 200.0, 15
    commission, slippage = model.apply(price, qty)
    assert commission == pytest.approx(abs(qty) * price * 0.001)
    assert slippage == pytest.approx(0.0)


def test_pct_of_value_negative_qty_uses_abs() -> None:
    model = PctOfValue(rate=0.001)
    assert model.apply(100.0, -10) == model.apply(100.0, 10)


def test_volume_slippage_combines_commission_and_slippage() -> None:
    model = VolumeSlippage(commission=1.0, slippage_rate=0.0002)
    price, qty = 250.0, 20
    commission, slippage = model.apply(price, qty)
    assert commission == pytest.approx(1.0)
    assert slippage == pytest.approx(abs(qty) * price * 0.0002)


def test_get_cost_model_builds_working_instance() -> None:
    model = get_cost_model("flat_per_trade", {"commission": 2.0})
    assert isinstance(model, FlatPerTrade)
    assert model.apply(99.0, 7) == (2.0, 0.0)


def test_get_cost_model_registry_complete() -> None:
    assert set(COST_MODELS) == {"flat_per_trade", "pct_of_value", "volume_slippage"}


def test_get_cost_model_unknown_name_raises() -> None:
    with pytest.raises(ValueError):
        get_cost_model("does_not_exist", {})


def test_models_are_base_cost_models() -> None:
    for name in COST_MODELS:
        assert isinstance(get_cost_model(name), BaseCostModel)
