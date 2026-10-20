# Production plan, enforcement matrix, and MCP responsibilities

## Objective and non-goals
Build a persistent, high-frequency centralized-exchange **spot** arbitrage scanner for
MEXC, LBank, HTX, KuCoin, Binance, Bybit, Bitfinex, Gate.io, Groovex and XT.
Return at most ten evidence-backed, depth-executable opportunities after fees,
withdrawal costs, asset/chain identity and transfer-state verification.
This phase is read-only/paper-only: no orders, withdrawals, custody or signing.

## Real-time market comparison contract

Every scan row labelled **live** must be sourced from a direct exchange adapter and include a source/event timestamp when supplied by the venue, a local receive timestamp, source health, and calculated age. Missing, stale, future-dated, disconnected, sequence-invalid, or malformed observations are unavailable and must not be silently replaced with cached prices. The core candidate gate also rejects otherwise-fresh buy/sell books whose `Book.timestamp_ms` values differ by more than the configurable `max_timestamp_skew_ms` threshold (default 250 ms). In the current Binance/Bybit feed prototypes, this field is populated from local receive time so cross-venue skew uses a common local clock; adapters must preserve that contract or normalize timestamps before assessment. Boolean timestamps and invalid skew limits fail closed. CoinGecko and CoinMarketCap provide discovery and broad context; their aggregate prices/volumes are not live exchange-specific truth.

Each comparison should expose: (1) canonical token identity including chain/network and contract address where applicable; (2) exact spot listing status per exchange; (3) venue-specific current price and quote currency; (4) venue-specific 24-hour quote volume; (5) order-book spread, depth, and quantity-specific VWAP; and (6) evidence timestamps and source provenance. Symbol/name matches alone are insufficient. If quote currencies differ, raw prices are not directly comparable without an independently verified conversion price and cost model.

A displayed price spread is informational only. An executable candidate still requires synchronized fresh order books, canonical asset identity, verified network/transfer route and deposit/withdraw status, authoritative fee currency/rates, limits/minimums, depth-aware VWAP, latency/slippage reserves, and strictly positive net profit. Listing and volume are useful comparison fields but do not prove executable liquidity.

Transfer-route evidence must name the canonical network ID, explicitly denominate the withdrawal fee in the base asset, and include finite withdrawal/deposit minimums and maximums with a current source timestamp. The requested withdrawal amount must fit the withdrawal bounds, and the amount remaining after the base-asset withdrawal fee must fit the destination deposit bounds. Unknown bounds, network mismatches, malformed values, or a fee reported in quote/exchange-token units are rejected. The current route contract expects the normalized network ID to match the canonical chain ID; venue-specific labels must be normalized by an authoritative adapter before reaching this gate.

**Current coverage limitation:** the repository contains initial Binance and Bybit public WebSocket feed prototypes. It does not yet have verified native live adapters for all planned venues. Gate Info MCP snapshots can cross-check a point-in-time observation but cannot be counted as a continuously maintained feed. A venue must not be labelled live until its adapter passes sequencing, freshness, reconnect, fixture and live-acceptance checks. Redis can support timestamped cache/stream state, deduplication and persistence, but cached values never override source freshness gates. Superpowers/Build assist the test-first engineering workflow; they do not supply exchange truth or waive verification.

## Stage assessment (2026-10-20)
**P1 prototype with initial P3 verification rules and agent coordinator. Not production.**
Implemented in repo: Decimal depth math; Binance/Bybit feed prototypes; basic book
state classes; fail-closed verification interfaces; deterministic agent supervisor,
risk cap and audit records; tests and CI configuration.
Not evidenced complete: running tests/green CI; live feed acceptance; other 8 venues;
authoritative contract/network/deposit/withdraw/fee providers; persistent service/API;
dashboard; replay/failure injection; metrics/alerts; 24h soak. Do not advertise live
opportunities until these gates pass.

## Production order and exit criteria
P0 Foundation: schema, lint/type checks, unit tests and CI. Exit: CI green.
P1 Market-data integrity: venue-specific WS adapters; snapshot bootstrap; sequence
continuity/checksum where documented; reconnect/backoff; freshness/clock checks;
bounded queues; health metrics. Exit: captured-fixture tests + live acceptance per venue.
P2 Coverage: MEXC, LBank, HTX, KuCoin, Binance, Bybit, Bitfinex, Gate.io, Groovex,
XT. Exit: each adapter passes conformance tests. Groovex identity/docs must be verified;
unknown APIs remain explicitly unsupported.
P3 Identity/transfers/costs: venue market IDs; base/quote canonicalization; native-asset
rules; chain IDs + contracts where applicable; supported network mapping; current
deposit/withdraw status, limits, minimums and fees; source, timestamp, TTL. Trading fee
currency must be explicit. Current P&L math accepts quote-currency trading fees only; base-
asset or exchange-token fee models remain unsupported and fail closed. Exit: no candidate
without fresh independent evidence. CG/CMC are discovery/cross-check only,
never transfer-status authorities.
P4 Agentic continuous scanner: event-driven workers, bounded queues, stale-data circuit
breakers, candidate deduplication, persistence (Postgres/Redis selected by deployment),
API + dashboard, replayable audit. Exit: restart-safe, idempotent, measurable service.
P5 Release: unit/property/integration/replay/fault tests; secrets scan; dependency and
container scan; structured logs, metrics and alerts; runbooks; 24h+ paper soak. Exit:
zero unexplained sequence gaps, no stale/unsupported candidates, CI green, rollback tested.
P6 optional execution: separate explicit authorization and threat-model review only;
not part of current scope.

## Agent responsibilities
- Discovery agent: enumerates spot markets and candidate directions.
- Market-data agent: owns one venue adapter and book state; sequence gaps invalidate it.
- Identity agent: matches canonical asset and chain/contract evidence.
- Transfer agent: validates buy-side withdrawal, sell-side deposit, route, fee and limits.
- Cost agent: fee schedule, fee currency, slippage, transfer/latency reserves.
- Verification agent: deterministic hard gates; cannot be overruled by model output.
- Risk agent: notional, max exposure, freshness, minimum profit and kill switch.
- Supervisor: schedules/retries within budgets, combines versioned evidence, ranks top 10,
  records all decisions and escalates missing/stale/conflicting evidence.
- Operations agent: watches feed health, drift, reconnect storms, queue lag, API health,
  alerts and can disable candidate publication; never turns a red signal green.

Agentic means autonomous *research and orchestration*, not uncontrolled financial actions.
Every action has a budget, timeout, retry ceiling, evidence provenance, and audit record.
LLM suggestions are advisory; all financial eligibility is deterministic.

## MCP integration enforcement
The full connector registry, permitted evidence, forbidden authority, fallback behavior and
agentic usage pattern are specified in [MCP_GUIDANCE.md](MCP_GUIDANCE.md) and enforced by
src/scanner/mcp_policy.py plus tests/test_mcp_policy.py.

- CoinGecko/CMC: discover and prioritize token candidates only.
- Binance/Bybit/Gate Info: point-in-time public spot-book snapshots for adapter sanity checks;
  not persistent synchronized books, transfer status, fee proof or eligibility authority.
- Coinversa Pulse/The Coin Daily: optional context with source clocks and access/freshness checks.
- GitHub/Remote Desktop Commander/Superpowers/GodPrompt/LLM Agent Builder Copilot: bounded
  engineering and verification assistance. CI evidence must match the exact PR head.
- Hypawave: optional sanitized agent coordination only; received messages are untrusted input.
- TokenOS dApp Builder/OnChainDiligence: optional design or concrete supported-policy review,
  not scanner critical-path evidence or execution authorization.

All connectors are specialists, not a quorum. Preserve provenance and limitations; conflicts,
missing clocks, unavailable access, and stale or malformed output cause rejection/escalation.
No external MCP may override deterministic eligibility or authorize execution. MCP connectors
used in ChatGPT are not automatically embedded into the deployed scanner runtime.

## Required candidate audit fields
candidate_id, venues, venue symbols, canonical asset, chain/network, contracts or native
asset rule, book sequence/version, exchange and receive timestamps, book age, executable
quantity, buy/sell VWAP and quote notionals, fee rate + fee currency + source + observed_at (quote-currency only until additional fee models are implemented),
withdrawal fee + asset + source + observed_at, deposit/withdraw enabled state + source +
observed_at, net quote profit, risk policy version, rejection reason, agent decisions.
A symbol-only match or a price-only spread is never enough.

## Secrets and deployment
Public feeds require no keys. Never store credentials in source or chat. Use a deployment
secret manager; initially read-only permissions only. No withdrawal permission. Secrets,
Redis/Postgres URLs and alert tokens are not committed. Do not ask user to paste secrets.
