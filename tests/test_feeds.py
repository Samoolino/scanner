import pytest
from scanner.feeds import bootstrap_binance_book
from scanner.orderbooks import BinanceDepth, ResyncRequired


def test_binance_bootstrap_requires_bridge_event():
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {"bids": [["100", "1"]], "asks": [["101", "1"]], "lastUpdateId": 10}
    pending = [{"U": 12, "u": 13, "E": 1001, "b": [], "a": []}]
    with pytest.raises(ResyncRequired, match="bridge"):
        bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000)


def test_binance_bootstrap_applies_bridge_and_later_updates():
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {"bids": [["100", "1"]], "asks": [["101", "1"]], "lastUpdateId": 10}
    pending = [
        {"U": 9, "u": 10, "E": 999, "b": [["99", "1"]], "a": []},
        {"U": 11, "u": 12, "E": 1001, "b": [["100", "0"], ["99", "2"]], "a": []},
    ]
    book = bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000)
    assert state.sequence == 12
    assert book.bids[0][1] == __import__("decimal").Decimal("2")


def test_binance_bootstrap_rejects_unbounded_buffer():
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {"bids": [["100", "1"]], "asks": [["101", "1"]], "lastUpdateId": 10}
    pending = [{"U": 11, "u": 11, "E": 1001, "b": [], "a": []}] * 3
    with pytest.raises(ResyncRequired, match="buffer limit"):
        bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000, max_buffered_events=2)
