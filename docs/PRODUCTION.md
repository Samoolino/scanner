# Production line and release gates

## Original objective
A persistent, high-frequency **spot** scanner across MEXC, LBank, HTX,
KuCoin, Binance, Bybit, Bitfinex, Gate.io, Groovex, and XT, ranking up to
ten **real, executable, positive-net-profit** opportunities after asset,
chain, deposit/withdraw, order-book depth, and all fee checks.

## Current stage: P1 — prototype market-data ingestion (NOT production)

- P0: repository, core depth math, fee deductions, unit-test fixtures: implemented.
- P1: Binance and Bybit public WebSocket prototype: implemented, **not yet
  accepted against live exchange traffic**.
- P2: MEXC, KuCoin, Gate, HTX, LBank, Bitfinex, XT and Groovex adapters:
  pending. Groovex's actual exchange identity and API must be validated.
- P3: canonical token/contract/chain registry and continuously refreshed
  deposit/withdrawal + account fee ingestion: **verification interfaces
  implemented, authoritative data providers not integrated**.
- P4: streaming candidate discovery, Redis persistence, top-ten API/dashboard:
  pending.
- P5: replay tests, exchange failure injection, live paper-mode soak,
  observability, CI green, operational runbooks: pending.
- P6: optional trade execution: **not authorized or implemented**.

## Hard release gates

1. Snapshot/delta continuity, checksums where offered, exchange-specific
   sequencing, reconnection and resync proven against captured fixtures.
2. Independent token identity on BOTH venues (contract + chain, or explicit
   native-asset identity rules). Symbol equality is insufficient.
3. Confirmed withdrawal enabled at buy venue, deposit enabled at sell venue,
   SAME supported chain and sufficient fee/limit evidence.
4. Source-backed, fresh taker fees and withdrawal fees, plus transfer/latency
   reserve. Missing evidence means rejected, never assumed zero.
5. Depth-weighted executable quantity at BOTH venues and positive net quote.
6. Book timestamps within strict age limits; no crossed, empty or invalid
   books. Clock skew and delayed exchange timestamps handled.
7. Continuous 24h+ paper soak with recorded rejection reasons, reconnect
   rates, feed latency, sequence gaps, uptime and reproducible decisions.
8. Top-ten UI must distinguish *observed paper opportunities* from
   executable trades. A profitable snapshot does not guarantee fill or
   withdrawal completion.

## Deployment/credentials

No keys for public feeds. Later request **read-only** exchange credentials
via secret store for authenticated fee/account/transfer metadata when needed.
Never commit API keys or enable withdrawals. Redis requires deployment
endpoint/credentials if external. No live orders in this phase.
