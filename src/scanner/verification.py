"""Explicitly sourced market identity and transfer-route evidence.

Unknown, stale, or disabled facts are NEVER interpreted as verified.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from scanner.core import Book, Costs, assess

@dataclass(frozen=True)
class AssetIdentity:
    venue: str
    symbol: str
    chain_id: str
    contract: str
    source: str
    verified_at_ms: int

@dataclass(frozen=True)
class TransferRoute:
    source_venue: str
    destination_venue: str
    chain_id: str
    withdrawals_enabled: bool
    deposits_enabled: bool
    withdrawal_fee_base: Decimal
    source: str
    verified_at_ms: int
    # Native route identifier must be explicit and match the canonical chain ID.
    network_id: str = ""
    # Withdrawal fees and transfer bounds are denominated in base-asset units.
    withdrawal_fee_currency: str = ""
    min_withdrawal_base: Decimal | None = None
    max_withdrawal_base: Decimal | None = None
    min_deposit_base: Decimal | None = None
    max_deposit_base: Decimal | None = None

@dataclass(frozen=True)
class FeeEvidence:
    venue: str
    taker_rate: Decimal
    source: str
    verified_at_ms: int
    # Fee must be denominated in quote currency until other fee assets are modeled.
    fee_currency: str = ""

def fresh(observed_at_ms: int, now_ms: int, ttl_ms: int) -> bool:
    # bool is an int subclass in Python, but is never a valid timestamp or TTL.
    if any(not isinstance(value, int) or isinstance(value, bool)
           for value in (observed_at_ms, now_ms, ttl_ms)):
        return False
    if ttl_ms < 0 or observed_at_ms < 0 or now_ms < 0:
        return False
    return 0 <= now_ms - observed_at_ms <= ttl_ms

def verified_identity(a: AssetIdentity | None, b: AssetIdentity | None,
                      now_ms: int, ttl_ms: int) -> bool:
    if not isinstance(a, AssetIdentity) or not isinstance(b, AssetIdentity):
        return False
    text_fields = (
        a.venue, a.symbol, a.chain_id, a.contract, a.source,
        b.venue, b.symbol, b.chain_id, b.contract, b.source,
    )
    if not all(isinstance(value, str) and value.strip() for value in text_fields):
        return False
    if not (fresh(a.verified_at_ms, now_ms, ttl_ms)
            and fresh(b.verified_at_ms, now_ms, ttl_ms)):
        return False
    return (a.chain_id.strip().lower() == b.chain_id.strip().lower()
            and a.contract.strip().lower() == b.contract.strip().lower()
            and a.venue != b.venue)

def _valid_transfer_limits(route: TransferRoute) -> bool:
    """Require complete, finite, ordered limits; unknown bounds fail closed."""
    try:
        fee = Decimal(str(route.withdrawal_fee_base))
        minimums = (
            Decimal(str(route.min_withdrawal_base)),
            Decimal(str(route.min_deposit_base)),
        )
        maximums = (
            Decimal(str(route.max_withdrawal_base)),
            Decimal(str(route.max_deposit_base)),
        )
    except (InvalidOperation, TypeError, ValueError):
        return False
    values = (fee, *minimums, *maximums)
    if not all(value.is_finite() for value in values) or fee < 0:
        return False
    return all(minimum >= 0 and maximum > 0 and minimum <= maximum
               for minimum, maximum in zip(minimums, maximums))


def verified_route(route: TransferRoute | None, buy_venue: str, sell_venue: str,
                   chain_id: str, now_ms: int, ttl_ms: int) -> bool:
    if route is None:
        return False
    text_fields = (route.source, route.source_venue, route.destination_venue,
                   route.chain_id, route.network_id, route.withdrawal_fee_currency,
                   chain_id)
    return bool(
        all(isinstance(value, str) and value.strip() for value in text_fields)
        and route.source_venue == buy_venue
        and route.destination_venue == sell_venue
        and route.chain_id.strip().lower() == chain_id.strip().lower()
        and route.network_id.strip().lower() == chain_id.strip().lower()
        and route.withdrawals_enabled is True
        and route.deposits_enabled is True
        and _valid_transfer_limits(route)
        and isinstance(route.verified_at_ms, int)
        and not isinstance(route.verified_at_ms, bool)
        and fresh(route.verified_at_ms, now_ms, ttl_ms)
    )

def _base_currency(symbol: str) -> str | None:
    if not isinstance(symbol, str) or symbol.count("/") != 1:
        return None
    base, quote = (part.strip().upper() for part in symbol.split("/"))
    if not base or not quote or base == quote:
        return None
    return base


def _quote_currency(symbol: str) -> str | None:
    """Parse only the scanner canonical BASE/QUOTE symbol form."""
    if _base_currency(symbol) is None:
        return None
    return symbol.split("/")[1].strip().upper()

def evaluate_verified(buy: Book, sell: Book, quantity: Decimal,
                      buy_asset: AssetIdentity | None, sell_asset: AssetIdentity | None,
                      route: TransferRoute | None,
                      buy_fee: FeeEvidence | None, sell_fee: FeeEvidence | None,
                      now_ms: int, book_ttl_ms: int = 1500,
                      metadata_ttl_ms: int = 300000,
                      other_quote: Decimal = Decimal("0"),
                      reserve_quote: Decimal = Decimal("0")) -> dict:
    identity_ok = verified_identity(buy_asset, sell_asset, now_ms, metadata_ttl_ms)
    route_ok = bool(identity_ok and verified_route(route, buy.venue, sell.venue,
                      buy_asset.chain_id, now_ms, metadata_ttl_ms))
    if not identity_ok:
        return {"eligible": False, "reason": "asset_identity_unverified"}
    # Identity evidence is venue-scoped: two matching contracts from unrelated
    # venues must not be accepted as evidence for the books under evaluation.
    if buy_asset.venue != buy.venue or sell_asset.venue != sell.venue:
        return {"eligible": False, "reason": "asset_identity_venue_mismatch"}
    # Verified contract metadata must describe the base asset actually traded.
    # Matching two metadata records is insufficient if both refer to another token.
    market_base = _base_currency(buy.symbol)
    if market_base is None:
        return {"eligible": False, "reason": "quote_currency_unverified"}
    if (not isinstance(buy_asset.symbol, str)
            or not isinstance(sell_asset.symbol, str)
            or buy_asset.symbol.strip().upper() != market_base
            or sell_asset.symbol.strip().upper() != market_base):
        return {"eligible": False, "reason": "asset_identity_market_mismatch"}
    if not route_ok:
        return {"eligible": False, "reason": "transfer_route_unverified"}
    fee_records = (buy_fee, sell_fee)
    if not all(isinstance(record, FeeEvidence) for record in fee_records):
        return {"eligible": False, "reason": "trading_fee_unverified"}
    if not all(
        isinstance(record.venue, str) and record.venue.strip()
        and isinstance(record.source, str) and record.source.strip()
        and fresh(record.verified_at_ms, now_ms, metadata_ttl_ms)
        for record in fee_records
    ):
        return {"eligible": False, "reason": "trading_fee_unverified"}
    if buy_fee.venue != buy.venue or sell_fee.venue != sell.venue:
        return {"eligible": False, "reason": "trading_fee_venue_mismatch"}
    try:
        buy_rate = Decimal(str(buy_fee.taker_rate))
        sell_rate = Decimal(str(sell_fee.taker_rate))
    except (InvalidOperation, TypeError, ValueError):
        return {"eligible": False, "reason": "invalid_trading_fee"}
    if not all(rate.is_finite() and Decimal("0") <= rate < Decimal("1")
               for rate in (buy_rate, sell_rate)):
        return {"eligible": False, "reason": "invalid_trading_fee"}
    # Current P&L math applies taker fees to quote notional. Reject base-token,
    # exchange-token, or unknown fee currencies rather than silently misprice them.
    buy_quote_currency = _quote_currency(buy.symbol)
    sell_quote_currency = _quote_currency(sell.symbol)
    if not buy_quote_currency or not sell_quote_currency:
        return {"eligible": False, "reason": "quote_currency_unverified"}
    # Different quote assets are different markets; never compare their raw
    # notionals as if they shared a common unit of account.
    if buy_quote_currency != sell_quote_currency:
        return {"eligible": False, "reason": "market_mismatch"}
    if (not isinstance(buy_fee.fee_currency, str)
            or not isinstance(sell_fee.fee_currency, str)
            or buy_fee.fee_currency.strip().upper() != buy_quote_currency
            or sell_fee.fee_currency.strip().upper() != sell_quote_currency):
        return {"eligible": False, "reason": "trading_fee_currency_unverified"}
    base_currency = _base_currency(buy.symbol)
    if (base_currency is None or not isinstance(route.withdrawal_fee_currency, str)
            or route.withdrawal_fee_currency.strip().upper() != base_currency):
        return {"eligible": False, "reason": "withdrawal_fee_currency_unverified"}
    try:
        amount = Decimal(str(quantity))
        withdrawal_fee = Decimal(str(route.withdrawal_fee_base))
        min_withdrawal = Decimal(str(route.min_withdrawal_base))
        max_withdrawal = Decimal(str(route.max_withdrawal_base))
        min_deposit = Decimal(str(route.min_deposit_base))
        max_deposit = Decimal(str(route.max_deposit_base))
    except (InvalidOperation, TypeError, ValueError):
        return {"eligible": False, "reason": "transfer_amount_out_of_limits"}
    received_amount = amount - withdrawal_fee
    if (not amount.is_finite() or amount <= 0
            or amount < min_withdrawal or amount > max_withdrawal
            or received_amount < min_deposit or received_amount > max_deposit):
        return {"eligible": False, "reason": "transfer_amount_out_of_limits"}
    return assess(buy, sell, amount, Costs(buy_rate,
                  sell_rate, withdrawal_fee,
                  other_quote, reserve_quote), now_ms, book_ttl_ms, True, True)

def top_ten(candidates: list[dict]) -> list[dict]:
    """Rank only well-formed, eligible, positive-profit observations.

    A single malformed candidate must not crash ranking or prevent valid
    candidates from being shown. Non-finite and unparseable profits fail closed.
    """
    ranked: list[tuple[Decimal, dict]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("eligible") is not True:
            continue
        try:
            profit = Decimal(str(candidate.get("net_quote", "0")))
        except (InvalidOperation, TypeError, ValueError):
            continue
        if not profit.is_finite() or profit <= 0:
            continue
        ranked.append((profit, candidate))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ranked[:10]]
