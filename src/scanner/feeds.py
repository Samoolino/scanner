"""Public, read-only WebSocket collectors. No exchange credentials required.

Binance bootstrap buffers events while fetching a REST snapshot, applies only a
sequence-bridged event stream, and retries on gaps or resource-limit violations.
"""
import asyncio
import json
import time

from scanner.orderbooks import BinanceDepth, BybitDepth, ResyncRequired

BINANCE_WS = "wss://stream.binance.com:9443/ws"
BINANCE_REST = "https://api.binance.com/api/v3/depth"
BYBIT_WS = "wss://stream.bybit.com/v5/public/spot"
BINANCE_MAX_BUFFERED_EVENTS = 20_000
BINANCE_SNAPSHOT_TIMEOUT_SECONDS = 10


async def cancel_and_drain(task):
    """Cancel an abandoned background request and consume its terminal result."""
    if not task.done():
        task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def decode_json_object(payload, venue: str) -> dict:
    """Decode one WebSocket frame and reject valid JSON that is not an object."""
    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
        raise ResyncRequired(f"invalid JSON frame from {venue}") from exc
    if not isinstance(event, dict):
        raise ResyncRequired(f"{venue} frame must be a JSON object")
    return event


def bootstrap_binance_book(state, snapshot, pending, received_at_ms,
                           max_buffered_events=BINANCE_MAX_BUFFERED_EVENTS):
    """Install a REST snapshot only if buffered WS updates prove sequence continuity."""
    if max_buffered_events <= 0 or len(pending) > max_buffered_events:
        state.valid = False
        raise ResyncRequired("Binance bootstrap buffer limit exceeded")
    try:
        last_update_id = snapshot["lastUpdateId"]
        if type(last_update_id) is not int or last_update_id < 0:
            raise ValueError("invalid snapshot update ID")
        bridge_exists = False
        for event in pending:
            first, last = event["U"], event["u"]
            if (type(first) is not int or type(last) is not int
                    or first < 0 or last < 0 or first > last):
                raise ValueError("invalid buffered update ID")
            if first <= last_update_id + 1 <= last:
                bridge_exists = True
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        state.valid = False
        raise ResyncRequired("invalid Binance snapshot or buffered event") from exc
    if not bridge_exists:
        state.valid = False
        raise ResyncRequired("Binance snapshot bridge not established")

    # A failed replacement snapshot must never leave a previously valid book usable.
    state.valid = False
    try:
        bids, asks = snapshot["bids"], snapshot["asks"]
        state.snapshot(bids, asks, last_update_id, received_at_ms)
    except (KeyError, TypeError, ValueError, OverflowError, ResyncRequired) as exc:
        state.valid = False
        raise ResyncRequired("invalid Binance snapshot payload") from exc
    for event in pending:
        state.delta(
            event,
            received_at_ms=event.get("_scanner_received_at_ms", received_at_ms),
        )
    return state.export()


async def binance_books(symbol="BTCUSDT"):
    import aiohttp

    symbol = symbol.upper()
    while True:
        state = BinanceDepth("binance", symbol)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(
                    f"{BINANCE_WS}/{symbol.lower()}@depth@100ms", heartbeat=20
                ) as ws:
                    pending = []

                    async def receive():
                        msg = await ws.receive(timeout=30)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            raise ResyncRequired("socket closed")
                        return decode_json_object(msg.data, "Binance")

                    snapshot_task = asyncio.create_task(
                        asyncio.wait_for(
                            session.get(
                                BINANCE_REST,
                                params={"symbol": symbol, "limit": 5000},
                            ),
                            timeout=BINANCE_SNAPSHOT_TIMEOUT_SECONDS,
                        )
                    )
                    while not snapshot_task.done():
                        try:
                            event = await asyncio.wait_for(receive(), timeout=0.25)
                            event["_scanner_received_at_ms"] = int(time.time() * 1000)
                            pending.append(event)
                            if len(pending) > BINANCE_MAX_BUFFERED_EVENTS:
                                raise ResyncRequired("Binance bootstrap buffer limit exceeded")
                        except asyncio.TimeoutError:
                            pass
                        except Exception:
                            # A bad frame/socket error must not leave the REST task
                            # running after this connection attempt is abandoned.
                            await cancel_and_drain(snapshot_task)
                            raise

                    response = await snapshot_task
                    async with response:
                        response.raise_for_status()
                        snapshot = await response.json()

                    bootstrap_binance_book(
                        state, snapshot, pending, received_at_ms=int(time.time() * 1000)
                    )
                    yield state.export()
                    while True:
                        event = await receive()
                        state.delta(event, received_at_ms=int(time.time() * 1000))
                        yield state.export()
        except (aiohttp.ClientError, asyncio.TimeoutError, ResyncRequired, KeyError, ValueError):
            await asyncio.sleep(2)


async def bybit_books(symbol="BTCUSDT", depth=50):
    import aiohttp

    symbol = symbol.upper()
    while True:
        state = BybitDepth("bybit", symbol)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(BYBIT_WS, heartbeat=20) as ws:
                    await ws.send_json({"op": "subscribe", "args": [f"orderbook.{depth}.{symbol}"]})
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            raise ResyncRequired("socket closed")
                        event = decode_json_object(msg.data, "Bybit")
                        if event.get("topic") != f"orderbook.{depth}.{symbol}":
                            continue
                        state.message(event, received_at_ms=int(time.time() * 1000))
                        yield state.export(depth)
        except (aiohttp.ClientError, asyncio.TimeoutError, ResyncRequired, KeyError, ValueError):
            await asyncio.sleep(2)
