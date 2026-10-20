from decimal import Decimal

from scanner.market_evidence import MarketSnapshot, compare_live_markets
from scanner.verification import AssetIdentity


def snapshot(venue, price, volume, timestamp=10000, listed=True, symbol="ABC/USDT"):
    return MarketSnapshot(
        venue, symbol, Decimal(price), Decimal(volume), listed,
        venue + "-native-feed", timestamp, timestamp
    )


def asset(venue, chain="1", contract="0xabc", timestamp=10000):
    return AssetIdentity(venue, "ABC/USDT", chain, contract, venue + "-registry", timestamp)


def test_fresh_same_asset_comparison_exposes_price_volume_and_listing():
    result = compare_live_markets(
        snapshot("binance", "10", "1000000"),
        snapshot("bybit", "10.5", "250000"),
        asset("binance"), asset("bybit"), now_ms=10000
    )
    assert result["comparable"] is True
    assert result["price_spread_pct"] == Decimal("5")
    assert result["buy_quote_volume_24h"] == Decimal("1000000")
    assert result["sell_quote_volume_24h"] == Decimal("250000")
    assert result["both_listed"] is True
    assert result["executable_opportunity"] is False


def test_stale_observation_is_not_comparable():
    result = compare_live_markets(
        snapshot("binance", "10", "1000", timestamp=1),
        snapshot("bybit", "10.5", "2000"),
        asset("binance"), asset("bybit"), now_ms=10000, market_ttl_ms=5000
    )
    assert result == {"comparable": False, "reason": "market_price_stale"}


def test_different_quote_currencies_are_not_compared_without_conversion():
    result = compare_live_markets(
        snapshot("binance", "10", "1000", symbol="ABC/USDT"),
        snapshot("bybit", "10.5", "2000", symbol="ABC/USDC"),
        asset("binance"), asset("bybit"), now_ms=10000
    )
    assert result == {"comparable": False, "reason": "market_mismatch"}


def test_unlisted_market_is_rejected():
    result = compare_live_markets(
        snapshot("binance", "10", "1000"),
        snapshot("bybit", "10.5", "2000", listed=False),
        asset("binance"), asset("bybit"), now_ms=10000
    )
    assert result == {"comparable": False, "reason": "market_not_listed"}


def test_different_chain_or_contract_is_rejected():
    result = compare_live_markets(
        snapshot("binance", "10", "1000"),
        snapshot("bybit", "10.5", "2000"),
        asset("binance", chain="1", contract="0xabc"),
        asset("bybit", chain="56", contract="0xdef"),
        now_ms=10000
    )
    assert result == {"comparable": False, "reason": "asset_identity_unverified"}
