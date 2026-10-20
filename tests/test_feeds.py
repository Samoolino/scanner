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


@pytest.mark.parametrize("bad_snapshot_id", [True, 10.5, "10"])
def test_binance_bootstrap_rejects_coercible_snapshot_sequence_ids(bad_snapshot_id):
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {"bids": [["100", "1"]], "asks": [["101", "1"]], "lastUpdateId": bad_snapshot_id}
    pending = [{"U": 11, "u": 11, "E": 1001, "b": [], "a": []}]
    with pytest.raises(ResyncRequired):
        bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000)
    with pytest.raises(ResyncRequired):
        state.export()


def test_binance_bootstrap_rejects_float_update_ids():
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {"bids": [["100", "1"]], "asks": [["101", "1"]], "lastUpdateId": 10}
    pending = [{"U": 11.5, "u": 12, "E": 1001, "b": [], "a": []}]
    with pytest.raises(ResyncRequired):
        bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000)
    with pytest.raises(ResyncRequired):
        state.export()


def test_binance_bootstrap_missing_snapshot_levels_invalidates_existing_book():
    state = BinanceDepth("binance", "BTCUSDT")
    state.snapshot([["100", "1"]], [["101", "1"]], 10, 1000)
    malformed_snapshot = {"lastUpdateId": 10, "asks": [["101", "1"]]}
    pending = [{"U": 11, "u": 11, "E": 1001, "b": [], "a": []}]

    with pytest.raises(ResyncRequired, match="snapshot"):
        bootstrap_binance_book(state, malformed_snapshot, pending, received_at_ms=1000)
    with pytest.raises(ResyncRequired):
        state.export()



@pytest.mark.parametrize("payload", ["[]", "null", "42", '"text"'])
def test_websocket_json_frame_must_be_object(payload):
    from scanner.feeds import decode_json_object

    with pytest.raises(ResyncRequired, match="JSON object"):
        decode_json_object(payload, venue="bybit")


def test_websocket_invalid_json_is_resync_error():
    from scanner.feeds import decode_json_object

    with pytest.raises(ResyncRequired, match="invalid JSON"):
        decode_json_object("{not-json", venue="binance")



def test_cancel_and_drain_snapshot_task():
    import asyncio
    from scanner.feeds import cancel_and_drain

    async def check():
        started = asyncio.Event()

        async def pending_request():
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(pending_request())
        await started.wait()
        await cancel_and_drain(task)
        assert task.cancelled()

    asyncio.run(check())



def test_cancel_and_drain_consumes_completed_task_exception():
    import asyncio
    from scanner.feeds import cancel_and_drain

    async def check():
        async def failed_request():
            raise RuntimeError("request failed")

        task = asyncio.create_task(failed_request())
        await asyncio.sleep(0)
        assert task.done()
        await cancel_and_drain(task)
        assert task.exception() is not None

    asyncio.run(check())
