"""Deterministic agentic research pipeline. No LLM or order execution.

Each agent owns a bounded responsibility and emits an auditable decision.
External market context cannot override hard transfer/fee/orderbook gates.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from scanner.core import Book
from scanner.verification import AssetIdentity, TransferRoute, FeeEvidence, evaluate_verified, top_ten

@dataclass(frozen=True)
class EvidenceBundle:
    buy: Book
    sell: Book
    quantity: Decimal
    buy_asset: AssetIdentity | None = None
    sell_asset: AssetIdentity | None = None
    transfer: TransferRoute | None = None
    buy_fee: FeeEvidence | None = None
    sell_fee: FeeEvidence | None = None
    other_quote: Decimal = Decimal("0")
    reserve_quote: Decimal = Decimal("0")

@dataclass(frozen=True)
class AgentDecision:
    agent: str
    accepted: bool
    reason: str

@dataclass
class AuditRecord:
    candidate: str
    decisions: list[AgentDecision] = field(default_factory=list)
    result: dict = field(default_factory=dict)

class EvidenceProvider(Protocol):
    async def collect(self, buy_venue: str, sell_venue: str,
                      symbol: str, quantity: Decimal) -> EvidenceBundle: ...

class ResearchAgent:
    """Suggests market pairs; never certifies profitability."""
    def propose(self, books: list[Book]) -> list[tuple[Book, Book]]:
        return [(a, b) for a in books for b in books
                if a.venue != b.venue and a.symbol == b.symbol
                and a.bids and b.asks and a.asks and b.bids
                and b.bids[0][0] > a.asks[0][0]]

class VerificationAgent:
    """Deterministic gate: rejects missing contract, chain or route evidence."""
    def check(self, evidence: EvidenceBundle, now_ms: int) -> dict:
        return evaluate_verified(
            evidence.buy, evidence.sell, evidence.quantity,
            evidence.buy_asset, evidence.sell_asset, evidence.transfer,
            evidence.buy_fee, evidence.sell_fee, now_ms,
            other_quote=evidence.other_quote, reserve_quote=evidence.reserve_quote)

class RiskAgent:
    """Bounded paper-mode risk policy; never places trades."""
    def __init__(self, min_profit_quote: Decimal = Decimal("0"),
                 max_notional_quote: Decimal = Decimal("1000")):
        if min_profit_quote < 0 or max_notional_quote <= 0:
            raise ValueError("invalid risk policy")
        self.min_profit_quote = min_profit_quote
        self.max_notional_quote = max_notional_quote

    def check(self, evidence: EvidenceBundle, result: dict) -> AgentDecision:
        if not result.get("eligible"):
            return AgentDecision("risk", False, "upstream_rejected")
        notional = Decimal(result["buy_quote"])
        if notional > self.max_notional_quote:
            return AgentDecision("risk", False, "notional_limit")
        if Decimal(result["net_quote"]) <= self.min_profit_quote:
            return AgentDecision("risk", False, "profit_threshold")
        return AgentDecision("risk", True, "paper_candidate")

class SupervisorAgent:
    """Coordinates specialist agents; output is a paper observation only."""
    def __init__(self, risk: RiskAgent | None = None):
        self.verification = VerificationAgent()
        self.risk = risk or RiskAgent()

    def evaluate(self, evidence: EvidenceBundle, now_ms: int) -> AuditRecord:
        record = AuditRecord(
            candidate=f"{evidence.buy.venue}:{evidence.sell.venue}:{evidence.buy.symbol}")
        outcome = self.verification.check(evidence, now_ms)
        record.decisions.append(AgentDecision(
            "verification", bool(outcome.get("eligible")),
            str(outcome.get("reason", "unknown"))))
        risk = self.risk.check(evidence, outcome)
        record.decisions.append(risk)
        record.result = {**outcome, "eligible": bool(outcome.get("eligible") and risk.accepted),
                         "paper_only": True, "execution_authorized": False}
        if not risk.accepted:
            record.result["reason"] = risk.reason if outcome.get("eligible") else outcome.get("reason")
        return record

    def rank(self, records: list[AuditRecord]) -> list[dict]:
        return top_ten([{"candidate": r.candidate, **r.result} for r in records])
