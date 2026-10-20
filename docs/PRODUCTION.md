# Production plan, enforcement matrix, and MCP responsibilities

## Objective and non-goals
Build a persistent, high-frequency centralized-exchange **spot** arbitrage scanner for
MEXC, LBank, HTX, KuCoin, Binance, Bybit, Bitfinex, Gate.io, Groovex and XT.
Return at most ten evidence-backed, depth-executable opportunities after fees,
withdrawal costs, asset/chain identity and transfer-state verification.
This phase is read-only/paper-only: no orders, withdrawals, custody or signing.

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
deposit/withdraw status, limits, minimums and fees; source, timestamp, TTL. Exit: no
candidate without fresh independent evidence. CG/CMC are discovery/cross-check only,
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
- GitHub: source of truth for changes, CI, review, releases; no claiming tests pass without checks.
- Remote Desktop Commander: optional authorized machine for commands and soak; unavailable
  until a device is connected. Never assume a local environment exists.
- CoinGecko + CoinMarketCap: asset discovery and independent metadata cross-checks only.
- Coinversa Pulse + The Coin Daily: optional context/risk signals. These products cover
  derivatives/market research, not target CEX spot book/transfer truth; cannot veto hard
  verification positively or establish executable spread.
- TokenOS dApp Builder: optional future dashboard/on-chain spec; not in scanner critical path.
- OnChainDiligence: only inspect a concrete, explicitly proposed supported payment against
  supplied rules; no payment or receipt creation unless a real authorized transaction exists.
All connectors are optional specialists, not a quorum. Their evidence must include source,
observation time, subject/venue/chain and confidence/limitations. Conflicts cause rejection
or escalation. No external MCP data is allowed to override exchange-native truth.

## Required candidate audit fields
candidate_id, venues, venue symbols, canonical asset, chain/network, contracts or native
asset rule, book sequence/version, exchange and receive timestamps, book age, executable
quantity, buy/sell VWAP and quote notionals, fee rate + fee currency + source + observed_at,
withdrawal fee + asset + source + observed_at, deposit/withdraw enabled state + source +
observed_at, net quote profit, risk policy version, rejection reason, agent decisions.
A symbol-only match or a price-only spread is never enough.

## Secrets and deployment
Public feeds require no keys. Never store credentials in source or chat. Use a deployment
secret manager; initially read-only permissions only. No withdrawal permission. Secrets,
Redis/Postgres URLs and alert tokens are not committed. Do not ask user to paste secrets.
