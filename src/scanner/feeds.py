"""Public, read-only WebSocket collectors. No exchange credentials required.

Binance bootstrap buffers events while fetching REST snapshot, then applies
buffered deltas. On gaps, reconnect and bootstrap again.
"""
import asyncio
import json
import time
from scanner.orderbooks import BinanceDepth, BybitDepth, ResyncRequired

BINANCE_WS = "wss://stream.binance.com:9443/ws"
BINANCE_REST = "https://api.binance.com/api/v3/depth"
BYBIT_WS = "wss://stream.bybit.com/v5/public/spot"

async def binance_books(symbol="BTCUSDT"):
    import aiohttp
    symbol = symbol.upper()
    while True:
        state = BinanceDepth("binance", symbol)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(f"{BINANCE_WS}/{symbol.lower()}@depth@100ms", heartbeat=20) as ws:
                    pending = []
                    async def receive():
                        msg = await ws.receive(timeout=30)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            raise ResyncRequired("socket closed")
                        return json.loads(msg.data)
                    # Snapshot must be fetched while WS is active; queue WS updates
                    task = asyncio.create_task(session.get(BINANCE_REST, params={"symbol": symbol, "limit": 5000}))
                    while not task.done():
                        try:
                            pending.append(await asyncio.wait_for(receive(), timeout=0.25))
                        except asyncio.TimeoutError:
                            pass
                    response = await task
                    async with response:
                        response.raise_for_status()
                        snap = await response.json()
                    state.snapshot(snap["bids"], snap["asks"], snap["lastUpdateId"], int(time.time()*1000))
                    for event in pending:
                        state.delta(event)
                    # If buffered events did not bridge snapshot, resync rather than trust an unbridged book.
                    if not pending or max(int(e["u"]) for e in pending) <= state.sequence:
                        raise ResyncRequired("snapshot bridge not established")
                    yield state.export()
                    while True:
                        state.delta(await receive())
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
                        state.message(event)
                        yield state.export(depth)
        except (aiohttp.ClientError, asyncio.TimeoutError, ResyncRequired, KeyError, ValueError):
            await asyncio.sleep(2)
