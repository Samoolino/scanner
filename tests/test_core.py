from decimal import Decimal as D
import pytest
from scanner.core import Book, Costs, assess, executable

def book(venue, bid, ask, ts=1000, valid=True):
    return Book(venue, "ABC/USDT", ((D(str(bid)), D("10")),),
                ((D(str(ask)), D("10")),), ts, valid)

def costs():
    return Costs(D("0.001"), D("0.001"), D("0.1"), D("0.5"), D("1"))

def test_depth_walk_and_insufficient_depth():
    b = Book("a", "ABC/USDT", (), ((D("10"), D("2")), (D("12"), D("3"))), 1000, True)
    assert executable(b, "buy", D("4")) == D("44")
    with pytest.raises(ValueError, match="Insufficient"):
        executable(b, "buy", D("6"))

def test_positive_net_only_after_costs():
    result = assess(book("a", 10, 11), book("b", 15, 16),
                    D("2"), costs(), 1000, 100, True, True)
    assert result["eligible"] and D(result["net_quote"]) > 0

def test_unverified_identity_rejected():
    assert assess(book("a", 10, 11), book("b", 15, 16),
                  D("2"), costs(), 1000, 100, False, True)["reason"] == "asset_identity_unverified"

def test_unverified_transfer_rejected():
    assert assess(book("a", 10, 11), book("b", 15, 16),
                  D("2"), costs(), 1000, 100, True, False)["reason"] == "transfer_route_unverified"

def test_stale_and_broken_sequence_rejected():
    assert assess(book("a", 10, 11, 800), book("b", 15, 16),
                  D("2"), costs(), 1000, 100, True, True)["reason"] == "stale_orderbook"
    assert assess(book("a", 10, 11, valid=False), book("b", 15, 16),
                  D("2"), costs(), 1000, 100, True, True)["reason"] == "orderbook_sequence_invalid"

def test_fee_can_remove_apparent_spread():
    expensive = Costs(D("0.1"), D("0.1"), D("0"), D("0"), D("0"))
    result = assess(book("a", 10, 11), book("b", 12, 13),
                    D("2"), expensive, 1000, 100, True, True)
    assert not result["eligible"] and result["reason"] == "non_positive_net"

def test_withdrawal_exceeds_quantity():
    result = assess(book("a", 10, 11), book("b", 15, 16),
                    D("0.1"), costs(), 1000, 100, True, True)
    assert result["reason"] == "withdrawal_exceeds_quantity"


@pytest.mark.parametrize(
    "side,levels",
    [
        ("buy", ((D("10"), D("1")), (D("9"), D("1")))),
        ("buy", ((D("10"), D("1")), (D("10"), D("2")))),
        ("sell", ((D("9"), D("1")), (D("10"), D("1")))),
        ("sell", ((D("10"), D("1")), (D("10"), D("2")))),
    ],
)
def test_executable_rejects_unsorted_or_duplicate_levels(side, levels):
    bids = levels if side == "sell" else ((D("8"), D("1")),)
    asks = levels if side == "buy" else ((D("11"), D("1")),)
    malformed = Book("venue", "ABC/USDT", bids, asks, 1000, True)
    with pytest.raises(ValueError, match="ordering"):
        executable(malformed, side, D("1"))
