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


def bootstrap_binance_book(state, snapshot, pending, received_at_ms,
                           max_buffered_events=BINANCE_MAX_BUFFERED_EVENTS):
    """Install a REST snapshot only if buffered WS updates prove sequence continuity."""
    if max_buffered_events <= 0 or len(pending) > max_buffered_events:
        state.valid = False
        raise ResyncRequired("Binance bootstrap buffer limit exceeded")
    try:
        last_update_id = int(snapshot["lastUpdateId"])
        bridge_exists = any(
            int(event["U"]) <= last_update_id + 1 <= int(event["u"])
            for event in pending
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        state.valid = False
        raise ResyncRequired("invalid Binance snapshot or buffered event") from exc
    if not bridge_exists:
        state.valid = False
        raise ResyncRequired("Binance snapshot bridge not established")

    state.snapshot(snapshot["bids"], snapshot["asks"], last_update_id, received_at_ms)
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
                        return json.loads(msg.data)

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
                                snapshot_task.cancel()
                                raise ResyncRequired("Binance bootstrap buffer limit exceeded")
                        except asyncio.TimeoutError:
                            pass

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
                        event = json.loads(msg.data)
                        if event.get("topic") != f"orderbook.{depth}.{symbol}":
                            continue
                        state.message(event, received_at_ms=int(time.time() * 1000))
                        yield state.export(depth)
        except (aiohttp.ClientError, asyncio.TimeoutError, ResyncRequired, KeyError, ValueError):
            await asyncio.sleep(2)
