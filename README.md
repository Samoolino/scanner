# CEX depth scanner

Safety-first foundation for a multi-exchange spot market scanner with cross-venue token comparison and arbitrage verification.

## Real-time scan contract

Every scan result presented as **live** must be based on direct, venue-specific market observations with both exchange event/source time (when available) and local receive time. The UI/API must show venue, market symbol, price, observation age, source health, listing status, exchange-specific 24-hour quote volume, and order-book depth. Stale, future-dated, missing, malformed, or disconnected observations are marked unavailable and excluded; cached CoinGecko/CoinMarketCap values must never be silently presented as live exchange prices.

CoinGecko and CoinMarketCap are useful for token discovery, metadata cross-checks, and broad market context. They are not substitutes for native exchange feeds. Binance and Bybit have initial public WebSocket feed prototypes in this repository. Full real-time coverage across every planned exchange is **not yet implemented or verified**; a venue is only advertised as live after its native adapter passes sequence, freshness, reconnect, and fixture/live-acceptance tests. Gate Info MCP snapshots may support point-in-time diagnostics, but do not count as a persistent live feed in the deployed scanner.

## Comparison behavior

A cross-venue comparison should make the following visible and independently traceable:

- **Token identity:** canonical asset, chain/network ID, contract address where applicable, and native-asset rules. Matching symbols or names alone do not prove identity.
- **Exchange listing:** whether the exact spot market is listed and currently available on each venue, with source and observation time.
- **Live prices:** last/trade or best bid/ask values labeled by source and age. Price-only spread is indicative, not an executable opportunity.
- **Exchange volume and liquidity:** per-venue 24-hour quote volume plus order-book depth and executable VWAP for the requested quantity. Aggregate market volume is not exchange-specific liquidity.
- **Net opportunity:** fees in supported currencies, withdrawal costs and network, transfer availability, minimums/limits, slippage and latency reserves. Publish a positive opportunity only after all deterministic gates pass.

If quote currencies differ (for example, USDT versus USDC), do not compare raw prices or notionals without a verified conversion path and conversion-cost model. Unknown identity, listing, network, fee, transfer, book sequence, or freshness means fail closed.

## Current status

**Prototype; not yet an all-venue live scanner and not production-ready.** Implemented foundations include Decimal depth/profit math, Binance and Bybit public feed prototypes, book sequence validation, fail-closed verification interfaces, deterministic agent coordination, MCP role policy, tests and CI configuration. Production coverage still requires native adapters and acceptance evidence for all planned venues, authoritative token/listing/chain/transfer/fee providers, persistent service/API/dashboard, monitoring, replay/fault tests, and a 24-hour or longer paper soak.

Results from unit tests or point-in-time connector snapshots are synthetic/diagnostic and must not be presented as verified live opportunities. This phase is read-only and paper-only: no orders or withdrawals.

## Local verification

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Planned venues

MEXC, LBank, HTX, KuCoin, Binance, Bybit, Bitfinex, Gate.io, XT, and Groovex (identity/API support to be confirmed).

## Infrastructure and agent boundaries

Redis may be used for bounded, timestamped cache/stream state, deduplication, and operational coordination; it is not an authority for exchange truth, and stale cache entries must not pass live-data gates. Superpowers/Build workflows support test-first implementation and review, not market-data authority. Binance and Bybit native public feeds are exchange sources. Gate Info MCP is a point-in-time cross-check until a native, continuously validated Gate.io adapter is deployed.

## Credential policy

Public market-data WebSockets usually do not require API keys. Do not commit credentials. Exchange read-only keys may later be needed for account-specific fee tiers and deposit/withdrawal permissions. Never request withdrawal-enabled or trading-enabled keys for the research-only phase.

## Next milestones

1. Complete and conformance-test native WebSocket adapters for every supported venue.
2. Add authoritative token/chain/contract and per-exchange listing metadata.
3. Integrate source-timestamped exchange volume, order-book depth, fees and network costs.
4. Persist provenance, timestamps, source health, and audit records; add stale-feed alarms.
5. Run continuous paper-mode collection and publish at most ten candidates only when every eligibility gate passes.
