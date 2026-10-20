"""Exchange-specific depth state machines; fail closed on invalid continuity."""
from decimal import Decimal as D, InvalidOperation

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

    @staticmethod
    def _integer(value, field: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ResyncRequired(f"invalid {field}") from exc
        if parsed < 0:
            raise ResyncRequired(f"invalid {field}")
        return parsed

    def _apply(self, bids, asks):
        """Validate the complete delta before mutating either side."""
        parsed_changes = []
        try:
            for levels, changes in ((self.bids, bids), (self.asks, asks)):
                parsed = []
                for price_raw, qty_raw in changes:
                    price, qty = D(str(price_raw)), D(str(qty_raw))
                    if (not price.is_finite() or not qty.is_finite()
                            or price <= 0 or qty < 0):
                        raise ResyncRequired("invalid book level")
                    parsed.append((levels, price, qty))
                parsed_changes.extend(parsed)
        except ResyncRequired:
            self.valid = False
            raise
        except (InvalidOperation, TypeError, ValueError) as exc:
            self.valid = False
            raise ResyncRequired("invalid book level") from exc

        for levels, price, qty in parsed_changes:
            if qty == 0:
                levels.pop(price, None)
            else:
                levels[price] = qty

    def snapshot(self, bids, asks, sequence: int, timestamp_ms: int):
        self.valid = False
        self.bids, self.asks = {}, {}
        self.sequence = None
        self.timestamp_ms = None
        sequence = self._integer(sequence, "sequence")
        timestamp_ms = self._integer(timestamp_ms, "timestamp")
        self._apply(bids, asks)
        self.sequence = sequence
        self.timestamp_ms = timestamp_ms
        self.valid = True

    def export(self, depth: int = 200) -> Book:
        if not self.valid or self.timestamp_ms is None:
            raise ResyncRequired("book not synchronized")
        if depth <= 0:
            raise ValueError("depth must be positive")
        bids = tuple(sorted(self.bids.items(), reverse=True)[:depth])
        asks = tuple(sorted(self.asks.items())[:depth])
        if not bids or not asks or bids[0][0] >= asks[0][0]:
            self.valid = False
            raise ResyncRequired("invalid book: empty side or crossed spread")
        return Book(self.venue, self.symbol, bids, asks,
                    self.timestamp_ms, self.valid)


class BinanceDepth(DepthState):
    def delta(self, event: dict, received_at_ms: int | None = None):
        if not self.valid or self.sequence is None:
            raise ResyncRequired("snapshot required")
        try:
            first = self._integer(event["U"], "first update ID")
            last = self._integer(event["u"], "last update ID")
        except (KeyError, TypeError) as exc:
            self.valid = False
            raise ResyncRequired("invalid Binance sequence fields") from exc
        if first > last:
            self.valid = False
            raise ResyncRequired("invalid Binance sequence range")
        if last <= self.sequence:
            return
        # An update must bridge the next expected update ID.
        if first > self.sequence + 1 or last < self.sequence + 1:
            self.valid = False
            raise ResyncRequired("Binance sequence gap")
        try:
            timestamp = (self._integer(received_at_ms, "receive timestamp") if received_at_ms is not None\n                         else self._integer(event["E"], "event timestamp"))
            self._apply(event["b"], event["a"])
        except (KeyError, TypeError) as exc:
            self.valid = False
            raise ResyncRequired("invalid Binance delta payload") from exc
        self.sequence = last
        self.timestamp_ms = timestamp
        self.valid = True


class BybitDepth(DepthState):
    def message(self, event: dict, received_at_ms: int | None = None):
        try:
            data = event["data"]
            message_type = event["type"]
            update = self._integer(data["u"], "update ID")
            timestamp = (self._integer(received_at_ms, "receive timestamp") if received_at_ms is not None\n                         else self._integer(event["ts"], "timestamp"))
        except (KeyError, TypeError) as exc:
            self.valid = False
            raise ResyncRequired("invalid Bybit message") from exc

        if message_type == "snapshot" or update == 1:
            self.snapshot(data["b"], data["a"], update, timestamp)
            return
        if message_type != "delta" or not self.valid or self.sequence is None:
            raise ResyncRequired("Bybit snapshot required")
        if update <= self.sequence:
            return
        # Bybit update IDs are monotonic but not documented as contiguous.
        try:
            self._apply(data["b"], data["a"])
        except (KeyError, TypeError) as exc:
            self.valid = False
            raise ResyncRequired("invalid Bybit delta payload") from exc
        self.sequence = update
        self.timestamp_ms = timestamp
        self.valid = True
