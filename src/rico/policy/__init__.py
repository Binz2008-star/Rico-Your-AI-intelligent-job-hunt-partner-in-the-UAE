"""src/rico/policy/__init__.py

Rico Brain Policy Gateway - Phase 1

Central policy layer that ensures Rico:
1. Classifies requests into domains before AI fallback
2. Handles unsupported integrations deterministically
3. Routes account/billing/subscription requests correctly
4. Asks clarification for ambiguous mixed requests

Usage:
    from src.rico.policy import classify_request, PolicyDecision
    
    decision = classify_request("what is my plan?", has_auth=True)
    if decision.route == "account_service":
        # Handle subscription query
    elif decision.route == "unsupported":
        # Return deterministic unsupported tool response
    elif decision.route == "clarification":
        # Ask user to clarify
"""

from .domains import RicoDomain, DOMAIN_DISPLAY_NAMES, DOMAIN_DESCRIPTIONS
from .capabilities import (
    Capability,
    get_capability,
    is_capability_available,
    get_unsupported_message,
)
from .policy import PolicyDecision, PolicyGateway, classify_request, log_policy_decision

__all__ = [
    # Domains
    "RicoDomain",
    "DOMAIN_DISPLAY_NAMES",
    "DOMAIN_DESCRIPTIONS",
    # Capabilities
    "Capability",
    "get_capability",
    "is_capability_available",
    "get_unsupported_message",
    # Policy
    "PolicyDecision",
    "PolicyGateway",
    "classify_request",
    "log_policy_decision",
]

__version__ = "1.0.0"
