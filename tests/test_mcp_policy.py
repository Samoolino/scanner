from scanner.mcp_policy import MCP_POLICIES, may_accept_as_exchange_truth, policy_for


def test_all_requested_mcps_have_explicit_roles():
    expected = {
        "GitHub", "Remote Desktop Commander", "CoinGecko", "CoinMarketCap",
        "Coinversa Pulse", "The Coin Daily", "TokenOS dApp Builder",
        "OnChainDiligence", "Hypawave", "LLM Agent Builder Copilot",
        "Superpowers", "GodPrompt", "Bybit", "Gate Info", "Binance", "Redis",
    }
    assert {p.name for p in MCP_POLICIES} == expected


def test_advisory_and_engineering_mcps_cannot_prove_exchange_state():
    names = (
        "CoinGecko", "CoinMarketCap", "Coinversa Pulse", "The Coin Daily",
        "TokenOS dApp Builder", "OnChainDiligence", "GitHub",
        "Remote Desktop Commander", "Hypawave", "LLM Agent Builder Copilot",
        "Superpowers", "GodPrompt",
    )
    for name in names:
        assert not may_accept_as_exchange_truth(name)
        policy = policy_for(name)
        assert policy and not policy.may_authorize_execution
        assert not policy.may_prove_transfer_status
        assert not policy.may_satisfy_live_book_gate


def test_coingecko_and_cmc_are_advisors_not_exchange_truth():
    for name in ("CoinGecko", "CoinMarketCap"):
        policy = policy_for(name)
        assert policy is not None
        assert policy.advisory_scope
        assert "candidate" in policy.advisory_scope.lower()
        assert "order book" in policy.forbidden_authority.lower()
        assert not policy.may_prove_spot_liquidity
        assert not policy.may_prove_transfer_status
        assert not policy.may_authorize_execution


def test_exchange_snapshot_mcp_is_not_a_live_book_gate():
    for name in ("Binance", "Bybit", "Gate Info"):
        policy = policy_for(name)
        assert policy is not None
        assert policy.may_provide_spot_snapshot
        assert not policy.may_satisfy_live_book_gate
        assert not policy.may_prove_transfer_status
        assert not policy.may_authorize_execution
        assert not may_accept_as_exchange_truth(name)


def test_only_continuous_verified_native_adapter_can_satisfy_book_gate():
    assert not any(p.may_satisfy_live_book_gate for p in MCP_POLICIES)


def test_redis_is_infrastructure_not_market_truth():
    policy = policy_for("Redis")
    assert policy is not None
    assert "cache" in policy.advisory_scope.lower()
    assert not policy.may_provide_spot_snapshot
    assert not policy.may_prove_spot_liquidity
    assert not policy.may_prove_transfer_status
    assert not policy.may_satisfy_live_book_gate
    assert not policy.may_authorize_execution
    assert not may_accept_as_exchange_truth("Redis")
