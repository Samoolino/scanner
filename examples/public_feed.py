"""Print public books. NOT a verified arbitrage opportunity feed."""
import asyncio
import sys
from scanner.feeds import binance_books, bybit_books

async def main():
    venue = sys.argv[1] if len(sys.argv) > 1 else "bybit"
    symbol = sys.argv[2] if len(sys.argv) > 2 else "BTCUSDT"
    feed = binance_books(symbol) if venue == "binance" else bybit_books(symbol)
    async for book in feed:
        print(book.venue, book.symbol, book.timestamp_ms,
              "bid", book.bids[0] if book.bids else None,
              "ask", book.asks[0] if book.asks else None, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
