"""Chat layer — split out of ``src.rico_chat_api`` during the monolith refactor.

Modules here own intent routing, context building, and response formatting
logic that historically lived in the single ``RicoChatAPI`` class. Entry points
and orchestration remain in ``src.rico_chat_api`` (deprecation re-exports).
"""
