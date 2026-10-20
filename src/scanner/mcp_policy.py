"""Agentic strategy policy and connector boundaries."""
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
    may_prove_spot_liquidity: bool = False
    may_prove_transfer_status: bool = False
    may_authorize_execution: bool = False

MCP_POLICIES = (
    ConnectorPolicy("GitHub", EvidenceRole.POLICY_REVIEW),
    ConnectorPolicy("Remote Desktop Commander", EvidenceRole.POLICY_REVIEW),
    ConnectorPolicy("CoinGecko", EvidenceRole.TOKEN_METADATA),
    ConnectorPolicy("CoinMarketCap", EvidenceRole.TOKEN_METADATA),
    ConnectorPolicy("Coinversa Pulse", EvidenceRole.MARKET_CONTEXT),
    ConnectorPolicy("The Coin Daily", EvidenceRole.MARKET_CONTEXT),
    ConnectorPolicy("TokenOS dApp Builder", EvidenceRole.POLICY_REVIEW),
    ConnectorPolicy("OnChainDiligence", EvidenceRole.POLICY_REVIEW),
)

def policy_for(name: str) -> ConnectorPolicy | None:
    return next((p for p in MCP_POLICIES if p.name == name), None)

def may_accept_as_exchange_truth(name: str) -> bool:
    """No requested research/tooling MCP is an exchange-native truth provider."""
    p = policy_for(name)
    return bool(p and p.role == EvidenceRole.EXCHANGE_NATIVE)
