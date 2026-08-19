"""Tier 7 — the team: specialist agents Griffin can delegate to.

Each specialist (see marketing.py, youtube.py, research.py) is the same
brain as Griffin itself — a ConversationLoop plus a scoped ToolRegistry —
just pointed at a narrower job with its own system prompt. team.py is the
roster; griffin/tools/delegate.py is what lets the orchestrator reach it.
"""
