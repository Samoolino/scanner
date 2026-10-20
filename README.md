# CEX depth scanner

Initial safety-first Python foundation for a multi-exchange spot arbitrage scanner.

## Status

**Not a live scanner yet.** No WebSocket connectors, token/chain registry, deposit/withdrawal verification, fee ingestion, or trade execution are implemented. Results from unit tests are synthetic and must not be presented as live opportunities.

The core `assess` function rejects unverified asset identities, unverified transfer routes, invalid book sequences, stale books, insufficient depth, and non-positive net profit. Withdrawal fees are modeled in base units. Fees and book freshness must be independently verified before production use.

## Local verification

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Planned venues

MEXC, LBank, HTX, KuCoin, Binance, Bybit, Bitfinex, Gate.io, XT, and Groovex (identity/API support to be confirmed).

## Credential policy

Public market-data WebSockets usually do not require API keys. Do not commit credentials. Exchange read-only keys may later be needed for account-specific fee tiers and deposit/withdrawal permissions. Never request withdrawal-enabled or trading-enabled keys for the research-only phase.

## Next milestones

1. Implement and test native WebSocket adapters with snapshot/delta sequencing and reconnection.
2. Validate canonical assets via contracts, chain identifiers, and deposit/withdraw routes.
3. Integrate actual fees and network costs; distinguish pre-funded from transfer-based strategies.
4. Run continuous paper-mode collection with stale-feed and data-integrity alarms.
5. Publish top ten *only when* real observations pass every gate.
