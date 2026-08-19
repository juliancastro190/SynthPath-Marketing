"""The team roster: which specialist agents exist and what they're for.

Griffin (the orchestrator) reaches these by name via delegate_task
(griffin/tools/delegate.py). Nothing here runs on its own — every
specialist only acts when handed a task; there's no heartbeat wiring for
the team yet, that's a later step.
"""

from griffin.agents.marketing import build_marketing_agent
from griffin.agents.research import build_research_agent
from griffin.agents.youtube import build_youtube_agent


def build_team(config=None):
    agents = [
        build_marketing_agent(config),
        build_youtube_agent(config),
        build_research_agent(config),
    ]
    return {agent.name: agent for agent in agents}


SPECIALISTS = build_team()
