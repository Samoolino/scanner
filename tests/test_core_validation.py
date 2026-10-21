from decimal import Decimal as D

from scanner.core import Book, Costs, assess


def book(venue, bids=((D("10"), D("2")),), asks=((D("11"), D("2")),), ts=1000):
    return Book(venue, "ABC/USDT", bids, asks, ts, True)


def costs():
    return Costs(D("0.001"), D("0.001"), D("0"), D("0"), D("0"))


def check(buy, sell, quantity=D("1"), c=None, now=1000, max_age=100):
    return assess(buy, sell, quantity, c or costs(), now, max_age, True, True)


def test_rejects_unsorted_bid_levels():
    malformed = book("a", bids=((D("9"), D("1")), (D("10"), D("1"))))
    assert check(malformed, book("b"))["reason"] == "invalid_orderbook_levels"


def test_rejects_unsorted_ask_levels():
    malformed = book("a", asks=((D("12"), D("1")), (D("11"), D("1"))))
    assert check(malformed, book("b"))["reason"] == "invalid_orderbook_levels"


def test_rejects_non_finite_levels_even_beyond_top():
    malformed = book("a", asks=((D("11"), D("1")), (D("NaN"), D("1"))))
    assert check(malformed, book("b"))["reason"] == "invalid_orderbook_levels"


def test_rejects_zero_quantity_level():
    malformed = book("a", asks=((D("11"), D("0")),))
    assert check(malformed, book("b"))["reason"] == "invalid_orderbook_levels"


def test_rejects_fee_rate_at_or_above_one():
    invalid_costs = Costs(D("1"), D("0"), D("0"), D("0"), D("0"))
    assert check(book("a"), book("b"), c=invalid_costs)["reason"] == "invalid_cost"


def test_rejects_non_finite_costs_and_quantity():
    invalid_costs = Costs(D("NaN"), D("0"), D("0"), D("0"), D("0"))
    assert check(book("a"), book("b"), c=invalid_costs)["reason"] == "invalid_cost"
    assert check(book("a"), book("b"), quantity=D("NaN"))["reason"] == "invalid_quantity"


def test_rejects_future_timestamp_and_invalid_age_limit():
    assert check(book("a", ts=1001), book("b"))["reason"] == "stale_orderbook"
    assert check(book("a"), book("b"), max_age=-1)["reason"] == "invalid_freshness_limit"


def test_rejects_fresh_books_with_excessive_timestamp_skew():
    buy = book("a", ts=1000)
    sell = book("b", ts=800)
    result = assess(buy, sell, D("1"), costs(), 1000, 500, True, True,
                    max_timestamp_skew_ms=100)
    assert result["reason"] == "orderbook_timestamp_skew"


def test_accepts_fresh_books_within_timestamp_skew_limit():
    buy = book("a", ts=1000)
    sell = book("b", ts=950)
    result = assess(buy, sell, D("1"), costs(), 1000, 100, True, True,
                    max_timestamp_skew_ms=100)
    assert result["reason"] != "orderbook_timestamp_skew"


def test_rejects_boolean_book_timestamp():
    result = assess(book("a", ts=True), book("b", ts=1000), D("1"), costs(),
                    1000, 100, True, True)
    assert result["reason"] == "stale_orderbook"


def test_rejects_invalid_timestamp_skew_limit():
    result = assess(book("a"), book("b"), D("1"), costs(), 1000, 100,
                    True, True, max_timestamp_skew_ms=True)
    assert result["reason"] == "invalid_freshness_limit"
