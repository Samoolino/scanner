# Agentic production strategy — spot CEX scanner

## Principle
**Agentic orchestration, deterministic execution gates.** Agents can discover,
collect, explain, retry, and escalate. They may not hallucinate exchange state,
waive missing evidence, authorize transfers, or place orders.

## Specialist agents
1. **Discovery agent** enumerates supported spot pairs and proposes directions.
2. **Market-data agent** maintains native WebSocket snapshots and deltas,
   sequence continuity, timestamps and reconnect/backoff.
3. **Identity agent** reconciles chain IDs and token contracts on both venues.
4. **Transfer agent** confirms source withdrawal and destination deposit
   availability on the same chain; records fee and limits.
5. **Cost agent** obtains sourced taker rates, withdrawal costs and reserves.
6. **Verification agent** applies fail-closed contract/route/fee/depth gates.
7. **Risk agent** enforces maximum notional, freshness and minimum net profit.
8. **Supervisor agent** combines immutable evidence and decisions into a
   traceable paper-only ranked result.
9. **Operations agent (planned)** detects feed drift, resync failures and
   service health; escalates instead of silently treating gaps as valid.

## Tool boundaries
- **GitHub**: source, reviews and CI.
- **Remote Desktop Commander**: optional tests/soak on authorized host only.
- **CoinGecko/CoinMarketCap**: discovery and token metadata cross-checks;
  NOT proof of executable venue liquidity or deposit availability.
- **Coinversa Pulse/The Coin Daily**: optional research context, primarily
  derivatives/market intelligence; NEVER substitute for spot order books.
- **TokenOS dApp Builder**: optional future on-chain UX/specification; not
  required for centralized-exchange spot scanning.
- **OnChainDiligence**: optional policy inspection of explicitly proposed
  on-chain payments; does not prove CEX deposit/withdraw state or send funds.

## Autonomy and safety
The current `SupervisorAgent` is a **deterministic agentic coordinator**, not
an autonomous LLM trader. Its outputs carry `paper_only=true` and
`execution_authorized=false`. There are no private keys, order-placement
tools or automated withdrawals. Real exchange metadata providers and
continuous ingestion are still missing; do not label synthetic test
fixtures as live opportunities.

## Release ordering
P1 native WebSocket book integrity -> P2 venue coverage -> P3 verified
identity/transfer/fee evidence -> P4 persistent agent supervisor + API ->
P5 replay, monitoring and paper soak -> P6 separate opt-in execution review.
