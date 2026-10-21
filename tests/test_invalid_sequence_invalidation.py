import pytest
from scanner.orderbooks import BinanceDepth, BybitDepth, ResyncRequired


def test_invalid_binance_sequence_id_invalidates_book():
    state = BinanceDepth("binance", "BTCUSDT")
    state.snapshot([["100", "1"]], [["101", "1"]], 10, 1000)
    with pytest.raises(ResyncRequired):
        state.delta({"U": "bad", "u": 11, "E": 1001, "b": [], "a": []})
    with pytest.raises(ResyncRequired, match="not synchronized"):
        state.export()


def test_invalid_binance_timestamp_invalidates_book():
    state = BinanceDepth("binance", "BTCUSDT")
    state.snapshot([["100", "1"]], [["101", "1"]], 10, 1000)
    with pytest.raises(ResyncRequired):
        state.delta({"U": 11, "u": 11, "E": "bad", "b": [], "a": []})
    with pytest.raises(ResyncRequired, match="not synchronized"):
        state.export()


def test_invalid_bybit_update_id_invalidates_book():
    state = BybitDepth("bybit", "BTCUSDT")
    state.message({"type": "snapshot", "ts": 1000, "data": {"u": 5, "b": [["100", "1"]], "a": [["101", "1"]]}})
    with pytest.raises(ResyncRequired):
        state.message({"type": "delta", "ts": 1001, "data": {"u": "bad", "b": [], "a": []}})
    with pytest.raises(ResyncRequired, match="not synchronized"):
        state.export()


def test_invalid_bybit_timestamp_invalidates_book():
    state = BybitDepth("bybit", "BTCUSDT")
    state.message({"type": "snapshot", "ts": 1000, "data": {"u": 5, "b": [["100", "1"]], "a": [["101", "1"]]}})
    with pytest.raises(ResyncRequired):
        state.message({"type": "delta", "ts": "bad", "data": {"u": 6, "b": [], "a": []}})
    with pytest.raises(ResyncRequired, match="not synchronized"):
        state.export()
