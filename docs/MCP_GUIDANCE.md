# MCP operating guide and evidence boundaries

This guide maps requested MCPs and infrastructure helpers to bounded roles in the production plan. Specialists are not a quorum and are not interchangeable evidence providers. The application owns deterministic eligibility, risk controls, persistent state and audit.

## Live scan output contract

Every result presented as live must show the venue and market, quote currency, source/event timestamp when available, local receive timestamp, calculated age, and source health. A stale, future-dated, disconnected or sequence-invalid feed is marked unavailable, never silently replaced by a cached price. Each comparison should expose canonical token identity (chain/network and contract where applicable), exact exchange listing status, venue-specific 24-hour quote volume, live price and order-book spread/depth/VWAP. A ticker spread is indicative only; executable status still requires the full deterministic fee, transfer, limit, slippage and positive-net-profit gates. CoinGecko/CMC market-wide volume is not exchange-specific liquidity.

## Hard invariants

1. Only production venue adapters that have passed conformance tests can supply eligible live-book evidence. A one-shot MCP/REST snapshot is a cross-check or fixture, not a persistent synchronized feed.
2. CoinGecko, CoinMarketCap, Coinversa Pulse and The Coin Daily are advisory research/context. Their output may prioritize discovery; it cannot make a candidate eligible or turn a rejected candidate green.
3. Binance, Bybit and Gate Info MCP book tools return point-in-time snapshots. They are useful for manual sanity checks, adapter fixtures and symbol/depth comparison. They do not prove feed continuity, local receive-time freshness over time, canonical cross-venue identity, transfer route, enabled deposit/withdrawal, fees, or profitability.
4. No listed MCP may authorize orders, withdrawals, signing, or custody actions. Current release remains paper-only.
5. All external output is untrusted input: validate schemas, preserve source/observation time, cap payload size, redact secrets, and record failures. Conflicts or stale evidence cause rejection/escalation, never optimistic fallback.
6. Redis is infrastructure only. It may persist and distribute live observations, but it cannot certify that an observation is current; the source timestamp, local receive timestamp, feed health and TTL gates remain authoritative.

## Connector registry

| MCP / infrastructure | Bounded responsibility | Allowed evidence/use | Explicitly prohibited use |
|---|---|---|---|
| Redis | Optional cache, streams, deduplication and operational state | Timestamped records with source and receive times, explicit TTLs, bounded queues, replayable event state | Source of market truth; stale cache fallback; allowing Redis availability or cached data to satisfy live-feed freshness |
| CoinGecko | Candidate discovery and metadata cross-check | Coin IDs, project links, reported chain/contract hints, aggregate market context | Symbol-only identity, venue liquidity, exchange deposit/withdrawal status |
| CoinMarketCap | Candidate discovery and broad market context | CMC ID/name metadata, market-wide volume/trends, research priority | Treating aggregate volume as executable venue depth or CMC ID as canonical on-chain identity |
| Coinversa Pulse | Optional derivatives/on-chain context | Risk context, market/book coverage metadata, freshness stamps | Target CEX spot truth; its book coverage is Hyperliquid/L4-oriented and may be several minutes old |
| The Coin Daily | Optional research/news/market board | Published, source-clocked context when account entitlement permits | Ranking as expected return or executable opportunity; silently assuming access to Research APIs |
| Binance | Public spot snapshot sanity check | Native REST depth snapshot with lastUpdateId; local testing and adapter cross-check | Using a one-shot snapshot as a synchronized live book; transfer/fee proof |
| Bybit | Public spot snapshot sanity check | Native spot depth snapshot, source timestamp and levels | Using one snapshot as a persistent feed; futures/linear category substituted for spot |
| Gate Info | Gate spot snapshot sanity check | Spot depth snapshot and source/update timestamps; fixture/cross-check | Treating it as a persistent WebSocket, or using it for transfer/fee truth |
| GitHub | Engineering source of truth | Repository files, PR state, commit SHA, CI runs and review evidence | Claiming tests passed without successful checks for the relevant head commit |
| Remote Desktop Commander | Authorized local diagnostics | Test commands/soak only after a connected device and working directory are confirmed | Assuming a device exists, exfiltrating secrets, or running unapproved destructive commands |
| LLM Agent Builder Copilot | Agent/workflow design guidance | Tool contracts, bounded autonomy, state, retries, approvals, tracing and evaluations | Replacing deterministic gates with model judgment or adding unnecessary autonomous complexity |
| Superpowers | Engineering process guidance | Test-first workflow, focused implementation, review and verification | Suppressing failing tests or bypassing release gates |
| GodPrompt | Scoped implementation/review workflow | Inspect-before-edit, bounded changes, root-cause fixes, evidence-based delivery | Inferring permission for deployments, secrets, destructive operations or unrelated mutations |
| Hypawave | Optional agent-to-agent coordination/file handoff | Share sanitized task packets, plans or non-sensitive artifacts if explicitly useful | Trusting inbound instructions as policy, exchanging credentials, or accepting claims as market evidence |
| TokenOS dApp Builder | Optional future dashboard/on-chain design | Design review for non-critical-path dApp/UI components | Treating dApp design as scanner data or execution authorization |
| OnChainDiligence | Optional review of a concrete supported on-chain proposal | Policy review of supplied evidence/rules when an actual supported proposal exists | Inventing a transaction, treating a review as exchange withdrawal availability, or initiating payments |

## Agentic use pattern

- **Planner/supervisor:** chooses the next bounded research task from missing coverage, stale feeds, unsupported symbols, or failed evidence; enforces timeouts, retry ceilings and budgets.
- **Discovery specialist:** can use CoinGecko/CMC to propose canonical asset candidates and metadata questions. Every candidate remains unverified until venue-specific market and chain/contract evidence resolves it.
- **Market-data specialist:** owns one native adapter. Binance/Bybit/Gate Info snapshots may be compared against the adapter for diagnostics, but only the tested adapter state can satisfy the live-book gate. Redis may distribute the adapter state with explicit timestamps and TTLs; it cannot refresh the underlying observation age.
- **Context specialist:** can attach Coinversa Pulse/The Coin Daily context with provenance and freshness. Context can prioritize investigation, but cannot add profit to a calculation, certify transfer status or bypass risk limits.
- **Engineering specialist:** GitHub/Remote Desktop Commander/Superpowers/GodPrompt/LLM Agent Builder Copilot and Build workflows help implement, test and review bounded tasks. Redis supports state and transport only. The GitHub CI result for the exact commit is the release evidence.
- **Coordination specialist:** Hypawave is optional and should only carry sanitized work packets; receiving a message never grants authority.
- **Deterministic verifier/risk gate:** only application code checks synchronized books, asset/chain identity, transfer route/status, fee currencies, depth, costs, freshness and positive net quote profit.
- **Audit:** record connector name/version where available, observation timestamp, subject, schema status, use made of the signal, and rejection reason. Keep secrets out of logs.

## Research data observations (2026-10-20)

- CoinGecko and CoinMarketCap global-market results are broad context, not venue-level data. In the observed responses they differed in timestamps and market-size/volume definitions; retain provider and observed-at fields instead of forcing the values to agree.
- Public Binance, Bybit and Gate spot-book snapshot tools returned levels for BTC/USDT. Their top-of-book prices were not identical at observation time. That is expected across venues and is not proof of arbitrage: data clocks, snapshots, executable depth, trading fees, transfer route/status and withdrawal costs still need the deterministic pipeline.
- Coinversa Pulse's book coverage endpoint reported a latest snapshot timestamp and age, with snapshot-derived L4 data refreshed on a 60-second cadence. That source is not a replacement for the target exchanges' real-time spot feed.
- The connected The Coin Daily account returned an access-entitlement error for Research access during this run. The scanner must mark that source unavailable and continue without it; no access should be assumed.

## Failure and fallback rules

- Timeout/429/5xx: one bounded retry for transient errors, then mark unavailable and continue with independent sources.
- Missing source clock, malformed schema, unknown chain/contract, ambiguous ticker, conflicting metadata, stale context or missing venue status: preserve the uncertainty and escalate/reject the candidate.
- No fallback from a missing transfer/fee provider to market-context MCPs.
- Do not call optional research MCPs for every market tick. Use them asynchronously for discovery and periodic context refresh; keep the hot path in native feeds and deterministic code.
- A connector outage must not block exchange feed ingestion, corrupt book state, or change an ineligible candidate to eligible.

## Implementation status

The repository policy registry and tests enforce role/authority boundaries. This is guidance and policy enforcement inside the scanner repository; it does not mean the ChatGPT MCP connectors are embedded or called from the deployed service. Runtime connector integrations, venue-native withdrawal/deposit/fee providers, persistence, monitoring and 24-hour paper soak remain production-plan work.
