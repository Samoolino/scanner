"""Explicitly sourced market identity and transfer-route evidence.

Unknown, stale, or disabled facts are NEVER interpreted as verified.
"""
from dataclasses import dataclass
from decimal import Decimal
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

@dataclass(frozen=True)
class FeeEvidence:
    venue: str
    taker_rate: Decimal
    source: str
    verified_at_ms: int

def fresh(observed_at_ms: int, now_ms: int, ttl_ms: int) -> bool:
    return 0 <= now_ms - observed_at_ms <= ttl_ms

def verified_identity(a: AssetIdentity | None, b: AssetIdentity | None,
                      now_ms: int, ttl_ms: int) -> bool:
    if a is None or b is None:
        return False
    if not all((a.source, b.source, a.chain_id, b.chain_id, a.contract, b.contract)):
        return False
    if not (fresh(a.verified_at_ms, now_ms, ttl_ms)
            and fresh(b.verified_at_ms, now_ms, ttl_ms)):
        return False
    return (a.chain_id.strip().lower() == b.chain_id.strip().lower()
            and a.contract.strip().lower() == b.contract.strip().lower()
            and a.venue != b.venue)

def verified_route(route: TransferRoute | None, buy_venue: str, sell_venue: str,
                   chain_id: str, now_ms: int, ttl_ms: int) -> bool:
    return bool(route and route.source and route.source_venue == buy_venue
                and route.destination_venue == sell_venue
                and route.chain_id.lower() == chain_id.lower()
                and route.withdrawals_enabled and route.deposits_enabled
                and route.withdrawal_fee_base >= 0
                and fresh(route.verified_at_ms, now_ms, ttl_ms))

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
    if not route_ok:
        return {"eligible": False, "reason": "transfer_route_unverified"}
    if not buy_fee or not sell_fee or not all((
            buy_fee.source, sell_fee.source,
            fresh(buy_fee.verified_at_ms, now_ms, metadata_ttl_ms),
            fresh(sell_fee.verified_at_ms, now_ms, metadata_ttl_ms))):
        return {"eligible": False, "reason": "trading_fee_unverified"}
    if buy_fee.venue != buy.venue or sell_fee.venue != sell.venue:
        return {"eligible": False, "reason": "trading_fee_venue_mismatch"}
    if not (Decimal("0") <= buy_fee.taker_rate < 1
            and Decimal("0") <= sell_fee.taker_rate < 1):
        return {"eligible": False, "reason": "invalid_trading_fee"}
    return assess(buy, sell, quantity, Costs(buy_fee.taker_rate,
                  sell_fee.taker_rate, route.withdrawal_fee_base,
                  other_quote, reserve_quote), now_ms, book_ttl_ms, True, True)

def top_ten(candidates: list[dict]) -> list[dict]:
    """Never rank unverified or zero/negative-profit observations."""
    return sorted((c for c in candidates if c.get("eligible") is True
                   and Decimal(str(c.get("net_quote", "0"))) > 0),
                  key=lambda c: Decimal(str(c["net_quote"])), reverse=True)[:10]
