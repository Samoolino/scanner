"""Agentic strategy policy and connector boundaries.

Research MCPs can help discover assets and prioritize investigation, but only
exchange-native adapters may supply executable spot-market or transfer-state
evidence. Advisory data never satisfies a deterministic eligibility gate.
"""
from dataclasses import dataclass
from enum import Enum


class EvidenceRole(str, Enum):
    EXCHANGE_NATIVE = "exchange_native"
    TOKEN_METADATA = "token_metadata"
    MARKET_CONTEXT = "market_context"
    POLICY_REVIEW = "policy_review"


@dataclass(frozen=True)
class ConnectorPolicy:
    name: str
    role: EvidenceRole
    advisory_scope: str = "General research and review only."
    forbidden_authority: str = (
        "Exchange order books, spot liquidity, trading fees, deposit/withdrawal "
        "status, transfer routes, or execution authorization."
    )
    may_prove_spot_liquidity: bool = False
    may_prove_transfer_status: bool = False
    may_authorize_execution: bool = False


MCP_POLICIES = (
    ConnectorPolicy("GitHub", EvidenceRole.POLICY_REVIEW,
                    "Review repository code, CI, issues, and implementation evidence."),
    ConnectorPolicy("Remote Desktop Commander", EvidenceRole.POLICY_REVIEW,
                    "Assist with authorized local diagnostics and test execution."),
    ConnectorPolicy(
        "CoinGecko", EvidenceRole.TOKEN_METADATA,
        "Discover token candidates; cross-check project metadata and contract/chain "
        "claims; use market-cap and volume context to prioritize research candidates. "
        "All such signals are advisory and require venue-native verification.",
    ),
    ConnectorPolicy(
        "CoinMarketCap", EvidenceRole.TOKEN_METADATA,
        "Discover token candidates; cross-check project metadata and market-wide "
        "volume/trend context to prioritize research candidates. Market data is not "
        "venue-specific executable liquidity and cannot establish asset identity.",
    ),
    ConnectorPolicy("Coinversa Pulse", EvidenceRole.MARKET_CONTEXT,
                    "Provide market context only; never infer spot-book or transfer state."),
    ConnectorPolicy("The Coin Daily", EvidenceRole.MARKET_CONTEXT,
                    "Provide news and narrative context only; never infer spot-book or transfer state."),
    ConnectorPolicy("TokenOS dApp Builder", EvidenceRole.POLICY_REVIEW,
                    "Review architecture and dApp design only; cannot authorize scanner actions."),
    ConnectorPolicy("OnChainDiligence", EvidenceRole.POLICY_REVIEW,
                    "Review supported on-chain evidence only; does not replace exchange transfer checks."),
)


def policy_for(name: str) -> ConnectorPolicy | None:
    return next((p for p in MCP_POLICIES if p.name == name), None)


def may_accept_as_exchange_truth(name: str) -> bool:
    """No requested research/tooling MCP is an exchange-native truth provider."""
    p = policy_for(name)
    return bool(p and p.role == EvidenceRole.EXCHANGE_NATIVE)
