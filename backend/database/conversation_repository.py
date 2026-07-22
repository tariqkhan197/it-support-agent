"""
Conversation and preference repository.

Implements the "memory" requirements: remembering previous conversations
and user preferences across sessions. The Supervisor agent (built in a
later phase) will use this to load recent history before routing a
request to a specialist agent.
"""

from sqlalchemy.orm import Session, selectinload

from backend.database.models import Conversation, Message, UserPreference
from backend.models.conversation import ConversationCreate, MessageCreate, UserPreferenceSet
from backend.utils.exceptions import ITSupportAgentError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationNotFoundError(ITSupportAgentError):
    """Raised when a requested conversation ID does not exist."""


class ConversationRepository:
    """Persistence for chat conversations, messages, and user preferences."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # Conversations
    # ------------------------------------------------------------------ #
    def create_conversation(self, data: ConversationCreate) -> Conversation:
        conversation = Conversation(user_identifier=data.user_identifier)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info("Created conversation %s for user %s", conversation.id, data.user_identifier)
        return conversation

    def get_conversation(self, conversation_id: int) -> Conversation:
        conversation = (
            self.db.query(Conversation)
            .options(selectinload(Conversation.messages))
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conversation is None:
            raise ConversationNotFoundError(f"Conversation {conversation_id} not found")
        return conversation

    def get_or_create_active_conversation(self, user_identifier: str) -> Conversation:
        """
        Returns the user's most recently updated conversation, or creates a
        new one if none exists. Used by the chat endpoint so a user's
        session naturally continues instead of starting fresh every message.
        """
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.user_identifier == user_identifier)
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        if conversation is not None:
            return conversation
        return self.create_conversation(ConversationCreate(user_identifier=user_identifier))

    def list_conversations_for_user(self, user_identifier: str, limit: int = 20) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_identifier == user_identifier)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------ #
    # Messages
    # ------------------------------------------------------------------ #
    def add_message(self, conversation_id: int, data: MessageCreate) -> Message:
        conversation = self.get_conversation(conversation_id)  # raises if missing

        message = Message(
            conversation_id=conversation.id,
            role=data.role.value,
            content=data.content,
            agent_name=data.agent_name,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_recent_messages(self, conversation_id: int, limit: int = 20) -> list[Message]:
        """Most recent `limit` messages, in chronological order — used to build LLM context."""
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(messages))

    # ------------------------------------------------------------------ #
    # User preferences
    # ------------------------------------------------------------------ #
    def set_preference(self, data: UserPreferenceSet) -> UserPreference:
        existing = (
            self.db.query(UserPreference)
            .filter(
                UserPreference.user_identifier == data.user_identifier,
                UserPreference.key == data.key,
            )
            .first()
        )
        if existing is not None:
            existing.value = data.value
            self.db.commit()
            self.db.refresh(existing)
            return existing

        preference = UserPreference(
            user_identifier=data.user_identifier, key=data.key, value=data.value
        )
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def get_preferences(self, user_identifier: str) -> list[UserPreference]:
        return (
            self.db.query(UserPreference)
            .filter(UserPreference.user_identifier == user_identifier)
            .all()
        )

    def get_preferences_dict(self, user_identifier: str) -> dict[str, str]:
        """Convenience accessor used by agents to inject preferences into prompts."""
        return {p.key: p.value for p in self.get_preferences(user_identifier)}
