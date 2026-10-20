"""Fail-closed executable-depth calculations. No trade execution."""
from dataclasses import dataclass
from decimal import Decimal

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

def executable(book: Book, side: str, base_quantity: Decimal) -> Decimal:
    """Quote paid (buy) or received (sell), walking full depth."""
    if base_quantity <= 0 or side not in ("buy", "sell"):
        raise ValueError("Invalid quantity or side")
    levels = book.asks if side == "buy" else book.bids
    remaining = base_quantity
    quote = D("0")
    for price, available in levels:
        if price <= 0 or available <= 0:
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
    """Returns verified candidate or rejection reason. Assumes withdrawal fee in base asset."""
    if not same_asset_verified:
        return {"eligible": False, "reason": "asset_identity_unverified"}
    if not transfer_verified:
        return {"eligible": False, "reason": "transfer_route_unverified"}
    if buy.venue == sell.venue or buy.symbol != sell.symbol:
        return {"eligible": False, "reason": "market_mismatch"}
    if not buy.bids or not buy.asks or not sell.bids or not sell.asks:
        return {"eligible": False, "reason": "empty_orderbook"}
    if (buy.bids[0][0] >= buy.asks[0][0]
            or sell.bids[0][0] >= sell.asks[0][0]):
        return {"eligible": False, "reason": "crossed_orderbook"}
    if not buy.sequence_valid or not sell.sequence_valid:
        return {"eligible": False, "reason": "orderbook_sequence_invalid"}
    if any(b.timestamp_ms > now_ms or now_ms - b.timestamp_ms > max_age_ms for b in (buy, sell)):
        return {"eligible": False, "reason": "stale_orderbook"}
    if any(x < 0 for x in (costs.buy_fee_rate, costs.sell_fee_rate,
                           costs.withdrawal_base, costs.other_quote, costs.reserve_quote)):
        return {"eligible": False, "reason": "invalid_cost"}
    if quantity <= costs.withdrawal_base:
        return {"eligible": False, "reason": "withdrawal_exceeds_quantity"}
    try:
        buy_quote = executable(buy, "buy", quantity)
        received_base = quantity - costs.withdrawal_base
        sell_quote = executable(sell, "sell", received_base)
    except ValueError as exc:
        return {"eligible": False, "reason": str(exc)}
    net = (sell_quote * (D("1") - costs.sell_fee_rate)
           - buy_quote * (D("1") + costs.buy_fee_rate)
           - costs.other_quote - costs.reserve_quote)
    return {"eligible": net > 0, "reason": "positive_net" if net > 0 else "non_positive_net",
            "net_quote": str(net), "buy_quote": str(buy_quote),
            "sell_quote": str(sell_quote), "base_received": str(received_base)}
