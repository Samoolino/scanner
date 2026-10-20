import pytest
from decimal import Decimal as D
from scanner.orderbooks import BinanceDepth, BybitDepth, ResyncRequired


def test_snapshot_rejects_bad_sequence_and_timestamp():
    state = BinanceDepth("binance", "BTCUSDT")
    with pytest.raises(ResyncRequired):
        state.snapshot([["100", "1"]], [["101", "1"]], -1, 1000)
    with pytest.raises(ResyncRequired):
        state.snapshot([["100", "1"]], [["101", "1"]], 1, -1)
    with pytest.raises(ResyncRequired):
        state.export()


def test_snapshot_rejects_non_numeric_levels_as_resync():
    state = BinanceDepth("binance", "BTCUSDT")
    with pytest.raises(ResyncRequired, match="invalid book level"):
        state.snapshot([["not-a-price", "1"]], [["101", "1"]], 1, 1000)


def test_export_rejects_empty_or_crossed_book():
    state = BinanceDepth("binance", "BTCUSDT")
    state.snapshot([["100", "1"]], [], 1, 1000)
    with pytest.raises(ResyncRequired, match="invalid book"):
        state.export()
    state.snapshot([["102", "1"]], [["101", "1"]], 2, 1000)
    with pytest.raises(ResyncRequired, match="invalid book"):
        state.export()


def test_bad_binance_delta_invalidates_book_atomically():
    state = BinanceDepth("binance", "BTCUSDT")
    state.snapshot([["100", "1"]], [["101", "1"]], 10, 1000)
    with pytest.raises(ResyncRequired):
        state.delta({"U": 11, "u": 11, "E": 1001, "b": [["99", "2"]], "a": [["oops", "1"]]})
    with pytest.raises(ResyncRequired):
        state.export()


def test_bybit_bad_delta_invalidates_book():
    state = BybitDepth("bybit", "BTCUSDT")
    state.message({"type": "snapshot", "ts": 1000, "data": {"u": 5, "b": [["100", "2"]], "a": [["101", "3"]]}})
    with pytest.raises(ResyncRequired):
        state.message({"type": "delta", "ts": 1001, "data": {"u": 6, "b": [["99", "-1"]], "a": []}})
    with pytest.raises(ResyncRequired):
        state.export()
