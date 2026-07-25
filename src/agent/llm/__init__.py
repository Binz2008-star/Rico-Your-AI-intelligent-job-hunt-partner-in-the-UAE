"""LLM-facing agent layer.

Holds the wire-format bridge between the model and Rico's existing tool
registry / agent runtime. Nothing in this package may execute a job action
directly — Class A tools are dispatched through ``agent_runtime.handle_action``
so idempotency, the audit log and the approval gate stay below the model.
"""
