"""General IT specialist agent (fallback/triage) — see backend/prompts/agent_prompts.py for its prompt."""

from backend.agents.base_agent import SpecialistAgent


class GeneralAgent(SpecialistAgent):
    category = "general"
