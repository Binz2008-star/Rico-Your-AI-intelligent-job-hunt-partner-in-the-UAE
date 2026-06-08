"""Golden scenarios for Rico evaluation.

Scenarios are stored in scenarios.jsonl in JSONL format.
Each scenario contains:
- id: unique identifier
- persona: user type (engineer, cautious, bilingual, etc.)
- goal: what the user wants to achieve
- type: happy_path, fallback, safety, language, etc.
- language: en, ar, mixed
- turns: list of conversation turns with expected outcomes
"""
