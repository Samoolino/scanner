from scanner.mcp_policy import MCP_POLICIES, may_accept_as_exchange_truth, policy_for

def test_all_requested_mcps_have_explicit_roles():
    expected = {"GitHub", "Remote Desktop Commander", "CoinGecko", "CoinMarketCap",
                "Coinversa Pulse", "The Coin Daily", "TokenOS dApp Builder",
                "OnChainDiligence"}
    assert {p.name for p in MCP_POLICIES} == expected

def test_research_connectors_cannot_prove_exchange_transfer_state():
    for name in ("CoinGecko", "CoinMarketCap", "Coinversa Pulse", "The Coin Daily",
                 "TokenOS dApp Builder", "OnChainDiligence", "GitHub",
                 "Remote Desktop Commander"):
        assert not may_accept_as_exchange_truth(name)
        policy = policy_for(name)
        assert policy and not policy.may_authorize_execution
