import pytest
from decimal import Decimal as D
from scanner.orderbooks import BinanceDepth, BybitDepth, ResyncRequired

def test_binance_snapshot_delta_zero_removes_level():
    s = BinanceDepth("binance", "BTC/USDT")
    s.snapshot([["100", "2"]], [["101", "3"]], 10, 1000)
    s.delta({"U": 11, "u": 12, "E": 1001, "b": [["100", "0"], ["99", "5"]], "a": []})
    b = s.export()
    assert b.bids == ((D("99"), D("5")),)
    assert s.sequence == 12

def test_binance_gap_invalidates_book():
    s = BinanceDepth("binance", "BTC/USDT")
    s.snapshot([["100", "2"]], [["101", "3"]], 10, 1000)
    with pytest.raises(ResyncRequired, match="gap"):
        s.delta({"U": 14, "u": 15, "E": 1001, "b": [], "a": []})
    with pytest.raises(ResyncRequired):
        s.export()

def test_binance_ignores_old_update():
    s = BinanceDepth("binance", "BTC/USDT")
    s.snapshot([["100", "2"]], [["101", "3"]], 10, 1000)
    s.delta({"U": 9, "u": 10, "E": 1001, "b": [["100", "0"]], "a": []})
    assert s.export().bids[0][1] == D("2")

def test_bybit_snapshot_delta_and_resnapshot():
    s = BybitDepth("bybit", "BTC/USDT")
    s.message({"type": "snapshot", "ts": 1000, "data": {"u": 5, "b": [["100", "2"]], "a": [["101", "3"]]}})
    s.message({"type": "delta", "ts": 1001, "data": {"u": 7, "b": [["100", "0"], ["99", "1"]], "a": []}})
    assert s.export().bids == ((D("99"), D("1")),)
    s.message({"type": "snapshot", "ts": 1002, "data": {"u": 8, "b": [["98", "4"]], "a": [["102", "2"]]}})
    assert s.export().bids == ((D("98"), D("4")),)

def test_bybit_requires_snapshot():
    with pytest.raises(ResyncRequired):
        BybitDepth("bybit", "BTC/USDT").message(
            {"type": "delta", "ts": 1000, "data": {"u": 5, "b": [], "a": []}})

def test_invalid_price_invalidates():
    s = BinanceDepth("binance", "BTC/USDT")
    with pytest.raises(ResyncRequired):
        s.snapshot([["NaN", "2"]], [], 10, 1000)
