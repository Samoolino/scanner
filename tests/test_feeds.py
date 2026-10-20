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



def test_cancel_and_drain_waits_for_task_finalizer():
    import asyncio
    from scanner.feeds import cancel_and_drain

    async def check():
        started = asyncio.Event()
        finalized = asyncio.Event()

        async def pending_request():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                finalized.set()

        task = asyncio.create_task(pending_request())
        await started.wait()
        await cancel_and_drain(task)
        assert task.cancelled()
        assert finalized.is_set()

    asyncio.run(check())



def test_binance_bootstrap_gap_after_bridge_invalidates_book():
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {
        "bids": [["100", "1"]],
        "asks": [["101", "1"]],
        "lastUpdateId": 10,
    }
    pending = [
        {"U": 11, "u": 11, "E": 1001, "b": [], "a": []},
        {"U": 13, "u": 13, "E": 1003, "b": [["100", "2"]], "a": []},
    ]

    with pytest.raises(ResyncRequired, match="sequence gap"):
        bootstrap_binance_book(state, snapshot, pending, received_at_ms=1000)
    with pytest.raises(ResyncRequired, match="synchronized"):
        state.export()



def test_binance_feed_cancellation_drains_snapshot_request(monkeypatch):
    import asyncio
    import sys
    from types import SimpleNamespace
    from scanner.feeds import binance_books

    async def check():
        request_started = asyncio.Event()
        request_finalized = asyncio.Event()
        receive_started = asyncio.Event()

        class FakeWebSocket:
            async def receive(self, timeout=None):
                receive_started.set()
                await asyncio.Event().wait()

        class FakeWebSocketContext:
            async def __aenter__(self):
                return FakeWebSocket()

            async def __aexit__(self, *args):
                return False

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def ws_connect(self, *args, **kwargs):
                return FakeWebSocketContext()

            async def get(self, *args, **kwargs):
                request_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    request_finalized.set()

        fake_aiohttp = SimpleNamespace(
            ClientSession=FakeSession,
            WSMsgType=SimpleNamespace(TEXT=1),
            ClientError=RuntimeError,
        )
        monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)
        feed = binance_books()
        consumer = asyncio.create_task(anext(feed))
        await request_started.wait()
        await receive_started.wait()
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass
        assert request_finalized.is_set()
        await feed.aclose()

    asyncio.run(check())



def test_binance_bootstrap_recovers_after_sequence_gap_with_fresh_snapshot():
    state = BinanceDepth("binance", "BTCUSDT")
    initial_snapshot = {
        "bids": [["100", "1"]],
        "asks": [["101", "1"]],
        "lastUpdateId": 10,
    }
    broken_pending = [
        {"U": 11, "u": 11, "E": 1001, "b": [], "a": []},
        {"U": 13, "u": 13, "E": 1003, "b": [], "a": []},
    ]
    with pytest.raises(ResyncRequired, match="sequence gap"):
        bootstrap_binance_book(state, initial_snapshot, broken_pending, received_at_ms=1000)
    with pytest.raises(ResyncRequired):
        state.export()

    fresh_snapshot = {
        "bids": [["99", "2"]],
        "asks": [["102", "3"]],
        "lastUpdateId": 20,
    }
    fresh_pending = [
        {"U": 21, "u": 21, "E": 1004, "b": [["99", "4"]], "a": []},
    ]
    book = bootstrap_binance_book(state, fresh_snapshot, fresh_pending, received_at_ms=1004)

    assert state.sequence == 21
    assert book.bids[0][1] == __import__("decimal").Decimal("4")
    assert book.asks[0][0] == __import__("decimal").Decimal("102")



@pytest.mark.parametrize("bad_limit", [True, False, 1.5, 0, -1, "2", None])
def test_binance_bootstrap_rejects_invalid_buffer_limit(bad_limit):
    state = BinanceDepth("binance", "BTCUSDT")
    snapshot = {
        "bids": [["100", "1"]],
        "asks": [["101", "1"]],
        "lastUpdateId": 10,
    }
    pending = [{"U": 11, "u": 11, "E": 1001, "b": [], "a": []}]
    with pytest.raises(ResyncRequired, match="buffer limit"):
        bootstrap_binance_book(
            state, snapshot, pending, received_at_ms=1000,
            max_buffered_events=bad_limit,
        )
    with pytest.raises(ResyncRequired):
        state.export()
