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


def test_market_symbol_must_match_verified_venue_identity():
    mismatched = AssetIdentity("bybit", "ABC/BTC", "1", "0xabc", "bybit-registry", 10000)
    result = compare_live_markets(
        snapshot("binance", "10", "1000"),
        snapshot("bybit", "10.5", "2000"),
        asset("binance"), mismatched, now_ms=10000
    )
    assert result == {"comparable": False, "reason": "asset_identity_unverified"}


def test_malformed_identity_metadata_fails_closed_without_exception():
    malformed = AssetIdentity("bybit", None, None, None, "registry", 10000)
    result = compare_live_markets(
        snapshot("binance", "10", "1000"),
        snapshot("bybit", "10.5", "2000"),
        asset("binance"), malformed, now_ms=10000
    )
    assert result == {"comparable": False, "reason": "asset_identity_unverified"}



def test_malformed_market_text_fields_fail_closed_without_exception():
    from dataclasses import replace

    valid = snapshot("binance", "10", "1000")
    other = snapshot("bybit", "10.5", "2000")
    for malformed in (
        replace(valid, venue=None),
        replace(valid, symbol=None),
        replace(valid, source=None),
    ):
        result = compare_live_markets(
            malformed, other, asset("binance"), asset("bybit"), now_ms=10000
        )
        assert result == {"comparable": False, "reason": "market_price_stale"}


def test_boolean_timestamps_are_not_accepted_as_market_timestamps():
    from dataclasses import replace

    first = replace(snapshot("binance", "10", "1000"), observed_at_ms=True, received_at_ms=True)
    second = replace(snapshot("bybit", "10.5", "2000"), observed_at_ms=1, received_at_ms=1)
    result = compare_live_markets(
        first, second, asset("binance", timestamp=1), asset("bybit", timestamp=1),
        now_ms=1, market_ttl_ms=5000, metadata_ttl_ms=5000
    )
    assert result == {"comparable": False, "reason": "market_price_stale"}


def test_malformed_market_symbol_fails_closed_without_exception():
    from dataclasses import replace

    malformed = replace(snapshot("bybit", "10.5", "2000"), symbol=None)
    result = compare_live_markets(
        snapshot("binance", "10", "1000"), malformed,
        asset("binance"), asset("bybit"), now_ms=10000
    )
    assert result == {"comparable": False, "reason": "market_price_stale"}
