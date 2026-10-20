from decimal import Decimal as D
from scanner.core import Book
from scanner.verification import (
    AssetIdentity, TransferRoute, FeeEvidence, evaluate_verified,
    verified_identity, top_ten)

def book(venue, bid, ask, symbol="ABC/USDT"):
    return Book(venue, symbol, ((D(str(bid)), D("20")),),
                ((D(str(ask)), D("20")),), 1000, True)

def identity(venue, contract="0xabc", ts=1000):
    return AssetIdentity(venue, "ABC", "eip155:1", contract, "exchange_api", ts)

def route(deposits=True, withdrawals=True, ts=1000):
    return TransferRoute("buy", "sell", "eip155:1", withdrawals, deposits,
                         D("0.1"), "exchange_api", ts)

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
