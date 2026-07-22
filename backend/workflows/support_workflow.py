"""
Support workflow (LangGraph).

Graph shape:

    START -> guard_input -> supervisor -> retrieve_knowledge -> specialist(category) -> END

- guard_input:        validates/sanitizes the message and screens for prompt injection
- supervisor:          classifies the message into a category
- retrieve_knowledge:  (optional) queries the RAG vector store for relevant
                        company documentation to ground the specialist's answer
- specialist:          the matching SpecialistAgent produces the structured
                        TroubleshootingResponse, using retrieved context if available

State flows through a single TypedDict so every node can read/write it
without tight coupling to the others.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.agents.email_agent import EmailAgent
from backend.agents.general_agent import GeneralAgent
from backend.agents.networking_agent import NetworkingAgent
from backend.agents.printer_agent import PrinterAgent
from backend.agents.schemas import TroubleshootingResponse
from backend.agents.security_agent import SecurityAgent
from backend.agents.supervisor_agent import SupervisorAgent
from backend.agents.vpn_agent import VPNAgent
from backend.agents.windows_agent import WindowsAgent
from backend.knowledge_base.retrieval_service import RetrievalService
from backend.utils.exceptions import PromptInjectionDetectedError
from backend.utils.llm_client import LLMClient, LLMMessage
from backend.utils.logger import get_logger
from backend.utils.prompt_guard import validate_user_message

logger = get_logger(__name__)


class SupportWorkflowState(TypedDict, total=False):
    # ---- input ----
    user_message: str
    user_identifier: str
    conversation_history: list[LLMMessage]
    knowledge_base_context: str | None
    user_preferences: dict[str, str]

    # ---- computed during the run ----
    sanitized_message: str
    category: str
    routing_confidence: float
    routing_reasoning: str
    retrieved_sources: list[dict]
    response: TroubleshootingResponse | None
    error: str | None


def build_specialist_registry(llm_client: LLMClient) -> dict[str, Any]:
    """Instantiate all 7 specialists once, bound to the given LLM client."""
    return {
        "windows": WindowsAgent(llm_client),
        "networking": NetworkingAgent(llm_client),
        "printer": PrinterAgent(llm_client),
        "vpn": VPNAgent(llm_client),
        "email": EmailAgent(llm_client),
        "security": SecurityAgent(llm_client),
        "general": GeneralAgent(llm_client),
    }


def build_support_graph(llm_client: LLMClient, retrieval_service: RetrievalService | None = None):
    """
    Construct and compile the LangGraph state graph.

    A fresh graph is built per LLM client (production GroqLLMClient, or a
    FakeLLMClient in tests) so the whole pipeline is testable without
    network access. `retrieval_service` is optional — if omitted, the
    workflow simply skips RAG and specialists answer from general knowledge.
    """
    supervisor = SupervisorAgent(llm_client)
    specialists = build_specialist_registry(llm_client)

    def guard_input_node(state: SupportWorkflowState) -> dict:
        try:
            cleaned = validate_user_message(state["user_message"])
            return {"sanitized_message": cleaned, "error": None}
        except PromptInjectionDetectedError as exc:
            logger.warning("Input rejected by guardrail: %s", exc.message)
            return {"sanitized_message": "", "error": exc.message}

    def supervisor_node(state: SupportWorkflowState) -> dict:
        if state.get("error"):
            return {}  # short-circuit; input_guard already failed
        decision = supervisor.classify(state["sanitized_message"])
        return {
            "category": decision.category,
            "routing_confidence": decision.confidence,
            "routing_reasoning": decision.reasoning,
        }

    def retrieve_knowledge_node(state: SupportWorkflowState) -> dict:
        if state.get("error") or retrieval_service is None:
            return {}
        result = retrieval_service.retrieve(state["sanitized_message"])
        if not result.used_knowledge_base:
            return {"knowledge_base_context": None, "retrieved_sources": []}
        sources = [
            {
                "filename": c.source_filename,
                "page": c.page_number,
                "score": c.similarity_score,
            }
            for c in result.chunks
        ]
        return {"knowledge_base_context": result.context_text, "retrieved_sources": sources}

    def route_to_specialist(state: SupportWorkflowState) -> str:
        if state.get("error"):
            return END
        return state.get("category", "general")

    def make_specialist_node(category: str, agent):
        def _node(state: SupportWorkflowState) -> dict:
            response = agent.handle(
                user_message=state["sanitized_message"],
                conversation_history=state.get("conversation_history", []),
                knowledge_base_context=state.get("knowledge_base_context"),
                user_preferences=state.get("user_preferences", {}),
            )
            return {"response": response}
        return _node

    graph = StateGraph(SupportWorkflowState)
    graph.add_node("guard_input", guard_input_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("retrieve_knowledge", retrieve_knowledge_node)
    for category, agent in specialists.items():
        graph.add_node(category, make_specialist_node(category, agent))

    graph.set_entry_point("guard_input")
    graph.add_edge("guard_input", "supervisor")
    graph.add_edge("supervisor", "retrieve_knowledge")
    graph.add_conditional_edges(
        "retrieve_knowledge",
        route_to_specialist,
        {category: category for category in specialists} | {END: END},
    )
    for category in specialists:
        graph.add_edge(category, END)

    return graph.compile()


def run_support_workflow(
    *,
    llm_client: LLMClient,
    user_message: str,
    user_identifier: str,
    conversation_history: list[LLMMessage] | None = None,
    knowledge_base_context: str | None = None,
    user_preferences: dict[str, str] | None = None,
    retrieval_service: RetrievalService | None = None,
) -> SupportWorkflowState:
    """Convenience entrypoint: build the graph and run it once for a single turn."""
    graph = build_support_graph(llm_client, retrieval_service=retrieval_service)
    initial_state: SupportWorkflowState = {
        "user_message": user_message,
        "user_identifier": user_identifier,
        "conversation_history": conversation_history or [],
        "knowledge_base_context": knowledge_base_context,
        "user_preferences": user_preferences or {},
    }
    final_state = graph.invoke(initial_state)
    return final_state
