"""Exchange-specific depth state machines; fail closed on invalid continuity."""
from decimal import Decimal as D
from scanner.core import Book

class ResyncRequired(RuntimeError):
    pass

class DepthState:
    def __init__(self, venue: str, symbol: str):
        self.venue, self.symbol = venue, symbol
        self.bids, self.asks = {}, {}
        self.sequence = None
        self.timestamp_ms = None
        self.valid = False

    def _apply(self, bids, asks):
        for levels, changes in ((self.bids, bids), (self.asks, asks)):
            for price_raw, qty_raw in changes:
                price, qty = D(str(price_raw)), D(str(qty_raw))
                if not price.is_finite() or not qty.is_finite() or price <= 0 or qty < 0:
                    self.valid = False
                    raise ResyncRequired("invalid book level")
                if qty == 0:
                    levels.pop(price, None)
                else:
                    levels[price] = qty

    def snapshot(self, bids, asks, sequence: int, timestamp_ms: int):
        self.valid = False
        self.bids, self.asks = {}, {}
        self.sequence = None
        self._apply(bids, asks)
        self.sequence = int(sequence)
        self.timestamp_ms = int(timestamp_ms)
        self.valid = True

    def export(self, depth: int = 200) -> Book:
        if not self.valid or self.timestamp_ms is None:
            raise ResyncRequired("book not synchronized")
        if depth <= 0:
            raise ValueError("depth must be positive")
        return Book(self.venue, self.symbol,
                    tuple(sorted(self.bids.items(), reverse=True)[:depth]),
                    tuple(sorted(self.asks.items())[:depth]),
                    self.timestamp_ms, self.valid)

class BinanceDepth(DepthState):
    def delta(self, event: dict):
        if not self.valid or self.sequence is None:
            raise ResyncRequired("snapshot required")
        first, last = int(event["U"]), int(event["u"])
        if last <= self.sequence:
            return
        if first > self.sequence + 1 or last < self.sequence + 1:
            self.valid = False
            raise ResyncRequired("Binance sequence gap")
        self.valid = False
        self._apply(event["b"], event["a"])
        self.sequence = last
        self.timestamp_ms = int(event["E"])
        self.valid = True

class BybitDepth(DepthState):
    def message(self, event: dict):
        data = event["data"]
        if event["type"] == "snapshot" or int(data["u"]) == 1:
            self.snapshot(data["b"], data["a"], int(data["u"]), int(event["ts"]))
            return
        if event["type"] != "delta" or not self.valid or self.sequence is None:
            raise ResyncRequired("Bybit snapshot required")
        update = int(data["u"])
        if update <= self.sequence:
            return
        # Bybit update IDs are monotonic but not documented as contiguous.
        self.valid = False
        self._apply(data["b"], data["a"])
        self.sequence = update
        self.timestamp_ms = int(event["ts"])
        self.valid = True
