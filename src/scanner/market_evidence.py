"""Timestamped venue market metadata for informative live comparisons.

A comparable ticker spread is not an executable arbitrage signal. Order-book
VWAP and the deterministic verification gates remain authoritative.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from scanner.verification import AssetIdentity, fresh, verified_identity


@dataclass(frozen=True)
class MarketSnapshot:
    venue: str
    symbol: str
    last_price: Decimal
    quote_volume_24h: Decimal
    listed: bool
    source: str
    observed_at_ms: int
    received_at_ms: int


def _quote_currency(symbol: str) -> str | None:
    if not isinstance(symbol, str) or symbol.count("/") != 1:
        return None
    base, quote = (part.strip().upper() for part in symbol.split("/"))
    if not base or not quote or base == quote:
        return None
    return quote


def _base_asset(symbol: str) -> str | None:
    if not isinstance(symbol, str) or symbol.count("/") != 1:
        return None
    base, quote = (part.strip().upper() for part in symbol.split("/"))
    if not base or not quote or base == quote:
        return None
    return base


def _valid_market(market: MarketSnapshot, now_ms: int, ttl_ms: int) -> bool:
    if not all((market.venue, market.symbol, market.source)):
        return False
    if not isinstance(market.listed, bool):
        return False
    try:
        price = Decimal(str(market.last_price))
        volume = Decimal(str(market.quote_volume_24h))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if not price.is_finite() or price <= 0:
        return False
    if not volume.is_finite() or volume < 0:
        return False
    if not isinstance(market.observed_at_ms, int) or not isinstance(market.received_at_ms, int):
        return False
    return (fresh(market.observed_at_ms, now_ms, ttl_ms)
            and fresh(market.received_at_ms, now_ms, ttl_ms)
            and market.observed_at_ms <= market.received_at_ms)


def compare_live_markets(
    first: MarketSnapshot,
    second: MarketSnapshot,
    first_identity: AssetIdentity | None,
    second_identity: AssetIdentity | None,
    now_ms: int,
    market_ttl_ms: int = 5_000,
    metadata_ttl_ms: int = 300_000,
) -> dict:
    """Compare fresh venue tickers, but never authorize an executable trade."""
    if not _valid_market(first, now_ms, market_ttl_ms) or not _valid_market(
        second, now_ms, market_ttl_ms
    ):
        return {"comparable": False, "reason": "market_price_stale"}
    if not first.listed or not second.listed:
        return {"comparable": False, "reason": "market_not_listed"}
    first_base, second_base = _base_asset(first.symbol), _base_asset(second.symbol)
    first_quote, second_quote = _quote_currency(first.symbol), _quote_currency(second.symbol)
    if not first_base or not second_base or not first_quote or not second_quote:
        return {"comparable": False, "reason": "market_symbol_unverified"}
    if first_base != second_base or first_quote != second_quote:
        return {"comparable": False, "reason": "market_mismatch"}
    if first.venue == second.venue:
        return {"comparable": False, "reason": "venue_mismatch"}
    if first_identity is None or second_identity is None:
        return {"comparable": False, "reason": "asset_identity_unverified"}
    identity_text = (
        first_identity.venue, first_identity.symbol, first_identity.chain_id,
        first_identity.contract, first_identity.source, second_identity.venue,
        second_identity.symbol, second_identity.chain_id, second_identity.contract,
        second_identity.source,
    )
    if (not all(isinstance(value, str) and value.strip() for value in identity_text)
            or first_identity.venue != first.venue
            or second_identity.venue != second.venue
            or first_identity.symbol.strip().upper() != first.symbol.strip().upper()
            or second_identity.symbol.strip().upper() != second.symbol.strip().upper()
            or _base_asset(first_identity.symbol) != first_base
            or _base_asset(second_identity.symbol) != second_base
            or not verified_identity(first_identity, second_identity, now_ms, metadata_ttl_ms)):
        return {"comparable": False, "reason": "asset_identity_unverified"}

    first_price = Decimal(str(first.last_price))
    second_price = Decimal(str(second.last_price))
    if first_price <= second_price:
        buy, sell = first, second
    else:
        buy, sell = second, first
    buy_price = Decimal(str(buy.last_price))
    sell_price = Decimal(str(sell.last_price))
    spread_pct = (sell_price - buy_price) / buy_price * Decimal("100")
    return {
        "comparable": True,
        "reason": None,
        "asset": first_base,
        "chain_id": first_identity.chain_id,
        "contract": first_identity.contract,
        "quote_currency": first_quote,
        "buy_venue": buy.venue,
        "sell_venue": sell.venue,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "price_spread_pct": spread_pct,
        "buy_quote_volume_24h": Decimal(str(buy.quote_volume_24h)),
        "sell_quote_volume_24h": Decimal(str(sell.quote_volume_24h)),
        "both_listed": True,
        "buy_observed_at_ms": buy.observed_at_ms,
        "sell_observed_at_ms": sell.observed_at_ms,
        "buy_received_at_ms": buy.received_at_ms,
        "sell_received_at_ms": sell.received_at_ms,
        "executable_opportunity": False,
    }
