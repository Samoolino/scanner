"""Fail-closed executable-depth calculations. No trade execution."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

D = Decimal


@dataclass(frozen=True)
class Book:
    venue: str
    symbol: str
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    timestamp_ms: int
    sequence_valid: bool


@dataclass(frozen=True)
class Costs:
    buy_fee_rate: Decimal
    sell_fee_rate: Decimal
    withdrawal_base: Decimal
    other_quote: Decimal
    reserve_quote: Decimal


def _finite_decimal(value) -> bool:
    try:
        return D(str(value)).is_finite()
    except (InvalidOperation, TypeError, ValueError):
        return False


def _valid_levels(levels, descending: bool) -> bool:
    """Require finite, positive, unique prices/quantities in best-to-worst order."""
    previous = None
    try:
        for raw_price, raw_quantity in levels:
            price, quantity = D(str(raw_price)), D(str(raw_quantity))
            if (not price.is_finite() or not quantity.is_finite()
                    or price <= 0 or quantity <= 0):
                return False
            if previous is not None:
                if descending and price >= previous:
                    return False
                if not descending and price <= previous:
                    return False
            previous = price
    except (InvalidOperation, TypeError, ValueError):
        return False
    return True


def executable(book: Book, side: str, base_quantity: Decimal) -> Decimal:
    """Quote paid (buy) or received (sell), walking full depth."""
    if side not in ("buy", "sell") or not _finite_decimal(base_quantity) or D(str(base_quantity)) <= 0:
        raise ValueError("Invalid quantity or side")
    levels = book.asks if side == "buy" else book.bids
    remaining = D(str(base_quantity))
    quote = D("0")
    for raw_price, raw_available in levels:
        price, available = D(str(raw_price)), D(str(raw_available))
        if (not price.is_finite() or not available.is_finite()
                or price <= 0 or available <= 0):
            raise ValueError("Invalid orderbook level")
        taken = min(remaining, available)
        quote += taken * price
        remaining -= taken
        if remaining == 0:
            return quote
    raise ValueError("Insufficient executable orderbook depth")


def assess(buy: Book, sell: Book, quantity: Decimal, costs: Costs,
           now_ms: int, max_age_ms: int, same_asset_verified: bool,
           transfer_verified: bool) -> dict:
    """Return an auditable candidate decision; assumes withdrawal fee is in base asset."""
    if not same_asset_verified:
        return {"eligible": False, "reason": "asset_identity_unverified"}
    if not transfer_verified:
        return {"eligible": False, "reason": "transfer_route_unverified"}
    if buy.venue == sell.venue or buy.symbol != sell.symbol:
        return {"eligible": False, "reason": "market_mismatch"}
    if not buy.sequence_valid or not sell.sequence_valid:
        return {"eligible": False, "reason": "orderbook_sequence_invalid"}
    if not buy.bids or not buy.asks or not sell.bids or not sell.asks:
        return {"eligible": False, "reason": "empty_orderbook"}
    if not all((_valid_levels(buy.bids, True), _valid_levels(buy.asks, False),
                _valid_levels(sell.bids, True), _valid_levels(sell.asks, False))):
        return {"eligible": False, "reason": "invalid_orderbook_levels"}
    if (buy.bids[0][0] >= buy.asks[0][0]
            or sell.bids[0][0] >= sell.asks[0][0]):
        return {"eligible": False, "reason": "crossed_orderbook"}
    if (not isinstance(max_age_ms, int) or max_age_ms < 0
            or not isinstance(now_ms, int)):
        return {"eligible": False, "reason": "invalid_freshness_limit"}
    try:
        timestamps = (int(buy.timestamp_ms), int(sell.timestamp_ms))
    except (TypeError, ValueError, OverflowError):
        return {"eligible": False, "reason": "stale_orderbook"}
    if any(ts < 0 or ts > now_ms or now_ms - ts > max_age_ms for ts in timestamps):
        return {"eligible": False, "reason": "stale_orderbook"}
    if not _finite_decimal(quantity) or D(str(quantity)) <= 0:
        return {"eligible": False, "reason": "invalid_quantity"}
    cost_values = (costs.buy_fee_rate, costs.sell_fee_rate, costs.withdrawal_base,
                   costs.other_quote, costs.reserve_quote)
    if not all(_finite_decimal(value) for value in cost_values):
        return {"eligible": False, "reason": "invalid_cost"}
    buy_fee, sell_fee, withdrawal, other_quote, reserve = map(D, map(str, cost_values))
    if (buy_fee < 0 or sell_fee < 0 or buy_fee >= 1 or sell_fee >= 1
            or withdrawal < 0 or other_quote < 0 or reserve < 0):
        return {"eligible": False, "reason": "invalid_cost"}
    quantity = D(str(quantity))
    if quantity <= withdrawal:
        return {"eligible": False, "reason": "withdrawal_exceeds_quantity"}
    try:
        buy_quote = executable(buy, "buy", quantity)
        received_base = quantity - withdrawal
        sell_quote = executable(sell, "sell", received_base)
    except ValueError as exc:
        return {"eligible": False, "reason": str(exc)}
    net = (sell_quote * (D("1") - sell_fee)
           - buy_quote * (D("1") + buy_fee)
           - other_quote - reserve)
    return {"eligible": net > 0, "reason": "positive_net" if net > 0 else "non_positive_net",
            "net_quote": str(net), "buy_quote": str(buy_quote),
            "sell_quote": str(sell_quote), "base_received": str(received_base)}
