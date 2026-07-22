"""Security specialist agent — see backend/prompts/agent_prompts.py for its prompt."""

from backend.agents.base_agent import SpecialistAgent


class SecurityAgent(SpecialistAgent):
    category = "security"
