from decimal import Decimal as D
import pytest
from scanner.core import Book
from scanner.verification import (
    AssetIdentity, TransferRoute, FeeEvidence, evaluate_verified,
    verified_identity, top_ten)

def book(venue, bid, ask, symbol="ABC/USDT"):
    return Book(venue, symbol, ((D(str(bid)), D("20")),),
                ((D(str(ask)), D("20")),), 1000, True)

def identity(venue, contract="0xabc", ts=1000):
    return AssetIdentity(venue, "ABC", "eip155:1", contract, "exchange_api", ts)

def route(deposits=True, withdrawals=True, ts=1000, **overrides):
    values = {
        "network_id": "eip155:1",
        "withdrawal_fee_currency": "ABC",
        "min_withdrawal_base": D("0.5"),
        "max_withdrawal_base": D("100"),
        "min_deposit_base": D("0.5"),
        "max_deposit_base": D("100"),
    }
    values.update(overrides)
    return TransferRoute("buy", "sell", "eip155:1", withdrawals, deposits,
                         D("0.1"), "exchange_api", ts, **values)

def fee(venue, ts=1000, currency="USDT"):
    return FeeEvidence(venue, D("0.001"), "exchange_api", ts, currency)

def check(a=None, b=None, r=None, f1=None, f2=None):
    return evaluate_verified(book("buy", 10, 11), book("sell", 15, 16),
                             D("2"), a, b, r, f1, f2, 1000)

def test_identity_requires_contract_match_and_fresh_evidence():
    assert verified_identity(identity("buy"), identity("sell"), 1000, 100)
    assert not verified_identity(identity("buy"), identity("sell", "0xdef"), 1000, 100)
    assert not verified_identity(identity("buy", ts=0), identity("sell"), 1000, 100)

def test_missing_fee_blocks_candidate():
    result = check(identity("buy"), identity("sell"), route())
    assert result["reason"] == "trading_fee_unverified"

def test_disabled_deposit_blocks_candidate():
    result = check(identity("buy"), identity("sell"), route(deposits=False),
                   fee("buy"), fee("sell"))
    assert result["reason"] == "transfer_route_unverified"

def test_complete_evidence_can_pass():
    result = check(identity("buy"), identity("sell"), route(),
                   fee("buy"), fee("sell"))
    assert result["eligible"] and D(result["net_quote"]) > 0

def test_top_ten_excludes_unverified_and_sorts():
    rows = [{"eligible": True, "net_quote": str(i)} for i in range(15)]
    rows.append({"eligible": False, "net_quote": "100000"})
    result = top_ten(rows)
    assert len(result) == 10
    assert result[0]["net_quote"] == "14"
    assert result[-1]["net_quote"] == "5"


def test_unmodeled_trading_fee_currency_blocks_candidate():
    result = check(identity("buy"), identity("sell"), route(),
                   fee("buy", currency="ABC"), fee("sell", currency="USDT"))
    assert not result["eligible"]
    assert result["reason"] == "trading_fee_currency_unverified"


def test_missing_fee_currency_blocks_candidate():
    result = check(identity("buy"), identity("sell"), route(),
                   fee("buy", currency=""), fee("sell"))
    assert not result["eligible"]
    assert result["reason"] == "trading_fee_currency_unverified"


def test_malformed_symbol_blocks_fee_currency_assessment():
    malformed = Book("buy", "ABCUSDT", ((D("10"), D("20")),),
                     ((D("11"), D("20")),), 1000, True)
    result = evaluate_verified(malformed, book("sell", 15, 16), D("2"),
                               identity("buy"), identity("sell"), route(),
                               fee("buy"), fee("sell"), 1000)
    assert not result["eligible"]
    assert result["reason"] == "quote_currency_unverified"


def test_different_quote_currencies_are_rejected():
    result = evaluate_verified(book("buy", 10, 11, "ABC/USDT"),
                               book("sell", 15, 16, "ABC/USDC"), D("2"),
                               identity("buy"), identity("sell"), route(),
                               fee("buy", currency="USDT"), fee("sell", currency="USDC"), 1000)
    assert not result["eligible"]
    assert result["reason"] == "market_mismatch"


def test_route_requires_explicit_network_and_amount_limits():
    assert not check(identity("buy"), identity("sell"),
                     route(network_id=""), fee("buy"), fee("sell"))["eligible"]
    assert not check(identity("buy"), identity("sell"),
                     route(max_withdrawal_base=None), fee("buy"), fee("sell"))["eligible"]


def test_withdrawal_fee_must_be_denominated_in_base_asset():
    result = check(identity("buy"), identity("sell"),
                   route(withdrawal_fee_currency="USDT"), fee("buy"), fee("sell"))
    assert not result["eligible"]
    assert result["reason"] == "withdrawal_fee_currency_unverified"


def test_transfer_quantity_must_fit_withdrawal_and_deposit_limits():
    too_small = evaluate_verified(
        book("buy", 10, 11), book("sell", 15, 16), D("0.4"),
        identity("buy"), identity("sell"), route(), fee("buy"), fee("sell"), 1000)
    too_large = evaluate_verified(
        book("buy", 10, 11), book("sell", 15, 16), D("101"),
        identity("buy"), identity("sell"), route(), fee("buy"), fee("sell"), 1000)
    deposit_too_small_after_fee = evaluate_verified(
        book("buy", 10, 11), book("sell", 15, 16), D("0.6"),
        identity("buy"), identity("sell"),
        route(min_deposit_base=D("0.55")), fee("buy"), fee("sell"), 1000)
    assert too_small["reason"] == "transfer_amount_out_of_limits"
    assert too_large["reason"] == "transfer_amount_out_of_limits"
    assert deposit_too_small_after_fee["reason"] == "transfer_amount_out_of_limits"


def test_identity_boolean_timestamps_are_rejected():
    assert not verified_identity(identity("buy", ts=True), identity("sell"), 1000, 100)
    assert not verified_identity(identity("buy"), identity("sell", ts=False), 1000, 100)


def test_identity_malformed_text_fields_fail_closed_without_exception():
    malformed = AssetIdentity("buy", "ABC", 123, "0xabc", "exchange_api", 1000)
    assert not verified_identity(malformed, identity("sell"), 1000, 100)


def test_identity_rejects_non_string_venue_and_empty_provenance():
    malformed_venue = AssetIdentity(123, "ABC", "eip155:1", "0xabc", "exchange_api", 1000)
    missing_source = AssetIdentity("sell", "ABC", "eip155:1", "0xabc", "", 1000)
    assert not verified_identity(identity("buy"), malformed_venue, 1000, 100)
    assert not verified_identity(identity("buy"), missing_source, 1000, 100)


def test_fresh_rejects_boolean_or_invalid_clock_inputs():
    from scanner.verification import fresh
    assert not fresh(True, 1000, 100)
    assert not fresh(1000, False, 100)
    assert not fresh(1000, 1000, True)
    assert not fresh(1000, 1000, -1)
    assert not fresh("1000", 1000, 100)


def test_fee_boolean_timestamps_fail_closed():
    result = check(identity("buy"), identity("sell"), route(),
                   fee("buy", ts=True), fee("sell"))
    assert not result["eligible"]
    assert result["reason"] == "trading_fee_unverified"


def test_fee_malformed_provenance_fails_closed():
    malformed = FeeEvidence("buy", D("0.001"), 123, 1000, "USDT")
    result = check(identity("buy"), identity("sell"), route(),
                   malformed, fee("sell"))
    assert not result["eligible"]
    assert result["reason"] == "trading_fee_unverified"


def test_fee_rates_must_be_finite_numeric_values():
    for invalid_rate in ("not-a-rate", True, D("NaN"), D("Infinity"), D("-0.001"), D("1")):
        result = check(identity("buy"), identity("sell"), route(),
                       FeeEvidence("buy", invalid_rate, "exchange_api", 1000, "USDT"),
                       fee("sell"))
        assert not result["eligible"]
        assert result["reason"] == "invalid_trading_fee"


@pytest.mark.parametrize("bad_profit", ["NaN", "Infinity", "-Infinity", "not-a-number", None, {}])
def test_top_ten_skips_malformed_profit_without_crashing(bad_profit):
    rows = [
        {"eligible": True, "net_quote": "3"},
        {"eligible": True, "net_quote": bad_profit},
        {"eligible": True, "net_quote": "2"},
    ]
    result = top_ten(rows)
    assert [row["net_quote"] for row in result] == ["3", "2"]


def test_top_ten_skips_non_mapping_and_missing_profit_candidates():
    rows = [
        {"eligible": True, "net_quote": "3"},
        None,
        {"eligible": True},
        {"eligible": True, "net_quote": "NaN"},
    ]
    result = top_ten(rows)
    assert [row["net_quote"] for row in result] == ["3"]
