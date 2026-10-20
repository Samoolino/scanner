from decimal import Decimal as D
from scanner.core import Book
from scanner.agents import EvidenceBundle, ResearchAgent, RiskAgent, SupervisorAgent
from scanner.verification import AssetIdentity, TransferRoute, FeeEvidence

def book(venue, bid, ask):
    return Book(venue, "ABC/USDT", ((D(bid), D("100")),),
                ((D(ask), D("100")),), 1000, True)

def complete():
    buy, sell = book("a", "10", "11"), book("b", "15", "16")
    return EvidenceBundle(
        buy, sell, D("2"),
        AssetIdentity("a", "ABC", "eip155:1", "0xabc", "api", 1000),
        AssetIdentity("b", "ABC", "eip155:1", "0xabc", "api", 1000),
        TransferRoute("a", "b", "eip155:1", True, True, D("0.1"), "api", 1000),
        FeeEvidence("a", D("0.001"), "api", 1000),
        FeeEvidence("b", D("0.001"), "api", 1000))

def test_supervisor_never_invents_missing_evidence():
    e = EvidenceBundle(book("a", "10", "11"), book("b", "15", "16"), D("2"))
    record = SupervisorAgent().evaluate(e, 1000)
    assert not record.result["eligible"]
    assert record.result["reason"] == "asset_identity_unverified"
    assert not record.result["execution_authorized"]

def test_complete_evidence_is_paper_only():
    record = SupervisorAgent().evaluate(complete(), 1000)
    assert record.result["eligible"]
    assert record.result["paper_only"]
    assert [d.agent for d in record.decisions] == ["verification", "risk"]

def test_risk_notional_cap_rejects():
    record = SupervisorAgent(RiskAgent(max_notional_quote=D("10"))).evaluate(complete(), 1000)
    assert not record.result["eligible"]
    assert record.result["reason"] == "notional_limit"

def test_research_proposes_only_directional_spread():
    proposals = ResearchAgent().propose([book("a", "10", "11"), book("b", "15", "16")])
    assert len(proposals) == 1
    assert proposals[0][0].venue == "a"

def test_ranking_drops_rejected_candidates():
    sup = SupervisorAgent()
    records = [sup.evaluate(complete(), 1000),
               sup.evaluate(EvidenceBundle(book("a", "10", "11"), book("b", "15", "16"), D("2")), 1000)]
    assert len(sup.rank(records)) == 1
