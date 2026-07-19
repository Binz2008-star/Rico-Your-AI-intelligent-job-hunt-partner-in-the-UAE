"""
src/agent/reasoning
External reasoning layer: structured, auditable execution state instead of
hidden chain-of-thought. See trace.py for the model and the privacy contract.
"""
from src.agent.reasoning.trace import (
    STATUS_BLOCKED,
    STATUS_DECIDED,
    STATUS_EXECUTED,
    STATUS_GATHERING,
    TRACE_SCHEMA_VERSION,
    Assumption,
    Contradiction,
    Decision,
    EvidenceItem,
    ReasoningTrace,
    Verification,
)

__all__ = [
    "Assumption",
    "Contradiction",
    "Decision",
    "EvidenceItem",
    "ReasoningTrace",
    "Verification",
    "STATUS_BLOCKED",
    "STATUS_DECIDED",
    "STATUS_EXECUTED",
    "STATUS_GATHERING",
    "TRACE_SCHEMA_VERSION",
]
