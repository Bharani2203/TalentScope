"""Storage and lifecycle management for Core Intelligence multi-turn conversations.

Provides:
- Stable conversation identifier tracking.
- Context preservation (active entities, target roles, selected skills, time range).
- Follow-up query resolution (pronouns 'it', 'that', 'this', entity-less questions).
- Multi-tenant and cross-user isolation.
- Explicit context clearing and staleness handling.
- In-memory thread-safe LRU store with optional single-document Firestore persistence.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.auth import AuthenticatedUser

logger = logging.getLogger(__name__)

# Pronouns and anaphoric references indicating follow-up context
PRONOUN_PATTERN = re.compile(
    r"\b(it|its|that|this|these|those|the skill|the role|this technology|the occupation|the position)\b",
    re.IGNORECASE,
)


class ConversationTurn(BaseModel):
    """Single turn recorded in a conversation history."""

    model_config = ConfigDict(extra="forbid")

    turn_id: str
    client_message_id: str | None = None
    user_message: str
    intent: str
    domain: str | None = None
    primary_entity: str | None = None
    resolved_entities: list[str] = Field(default_factory=list)
    comparison_entities: list[str] = Field(default_factory=list)
    target_role: str | None = None
    time_range: str | None = None
    selected_skills: list[str] = Field(default_factory=list)
    selected_companies: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    execution_status: str = "completed"
    answer_summary: str | None = None
    response_payload: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationState(BaseModel):
    """State record for a multi-turn conversation session."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    user_id: str
    company_id: str | None = None
    portal_type: str = "individual"
    domain: str | None = None
    title: str | None = None
    active_entity: str | None = None
    comparison_entities: list[str] = Field(default_factory=list)
    active_role: str | None = None
    time_range: str = "30d"
    selected_skills: list[str] = Field(default_factory=list)
    selected_companies: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationStore:
    """Thread-safe store for conversation sessions with user and tenant isolation."""

    _instance: ConversationStore | None = None
    _lock = threading.Lock()

    def __init__(self, ttl_seconds: float = 7200.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._conversations: dict[str, ConversationState] = {}
        self._access_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ConversationStore:
        """Singleton accessor for in-process conversation state."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def create_conversation(
        self,
        *,
        user_id: str,
        company_id: str | None = None,
        portal_type: str = "individual",
        domain: str | None = None,
        filters: dict[str, Any] | None = None,
        title: str | None = None,
        conversation_id: str | None = None,
    ) -> ConversationState:
        """Create and persist a new empty or initialized conversation session."""
        import uuid
        now = datetime.now(timezone.utc)
        cid = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        with self._access_lock:
            existing = self._conversations.get(cid)
            if existing is not None:
                if existing.user_id != user_id:
                    raise PermissionError(f"User {user_id} does not own conversation {cid}.")
                if existing.portal_type == "company" and existing.company_id and existing.company_id != company_id:
                    raise PermissionError(f"Company {company_id} does not own conversation {cid}.")
                return existing

            state = ConversationState(
                conversation_id=cid,
                user_id=user_id,
                company_id=company_id,
                portal_type=portal_type,
                domain=domain,
                filters=dict(filters or {}),
                title=title or "New Conversation",
                created_at=now,
                updated_at=now,
            )
            self._conversations[cid] = state

        try:
            from app.core.firebase import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                client.collection("intelligence_conversations").document(f"conv_{cid}").set(
                    state.model_dump(mode="json"),
                    merge=True,
                )
        except Exception as exc:
            logger.debug("Firestore create_conversation safely skipped: %s", exc)

        return state

    def get_turn_by_client_message_id(
        self,
        conversation_id: str,
        client_message_id: str,
        *,
        user_id: str,
        company_id: str | None = None,
    ) -> ConversationTurn | None:
        """Return existing turn if client_message_id was already processed in this conversation."""
        if not conversation_id or not client_message_id:
            return None
        state = self.get_conversation(conversation_id, user_id=user_id, company_id=company_id)
        if state is None:
            return None
        for turn in state.turns:
            if turn.client_message_id and turn.client_message_id == client_message_id:
                return turn
        return None

    def get_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        company_id: str | None = None,
        domain: str | None = None,
        portal_type: str | None = None,
    ) -> ConversationState | None:
        """Retrieve conversation state verifying user and company isolation."""
        if not conversation_id:
            return None

        with self._access_lock:
            state = self._conversations.get(conversation_id)

        # Check local memory first
        if state is not None:
            # Check user isolation
            if state.user_id != user_id:
                logger.warning(
                    "User %s attempted to access conversation %s owned by %s",
                    user_id,
                    conversation_id,
                    state.user_id,
                )
                return None
            # Check company isolation if company-scoped
            if state.portal_type == "company" and state.company_id and state.company_id != company_id:
                logger.warning(
                    "Company %s attempted to access conversation %s owned by company %s",
                    company_id,
                    conversation_id,
                    state.company_id,
                )
                return None
            if portal_type and state.portal_type != portal_type:
                return None
            if domain and (state.domain or "skill") != domain:
                return None
            return state

        # Check Firestore document if available
        try:
            from app.core.firebase import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                doc = client.collection("intelligence_conversations").document(f"conv_{conversation_id}").get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    if data.get("user_id") == user_id:
                        if data.get("portal_type") == "company" and data.get("company_id") and data.get("company_id") != company_id:
                            return None
                        if portal_type and data.get("portal_type", "individual") != portal_type:
                            return None
                        if domain and (data.get("domain") or "skill") != domain:
                            return None
                        state = ConversationState.model_validate(data)
                        with self._access_lock:
                            self._conversations[conversation_id] = state
                        return state
        except Exception as exc:
            logger.debug("Firestore conversation lookup safely skipped: %s", exc)

        return None

    def check_conversation_access(
        self,
        conversation_id: str,
        *,
        user_id: str,
        company_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """Check whether user_id and company_id are allowed to access conversation_id.

        Returns (True, None) if permitted or new conversation, or (False, reason_message) if access denied.
        """
        if not conversation_id:
            return True, None

        with self._access_lock:
            state = self._conversations.get(conversation_id)

        if state is None:
            try:
                from app.core.firebase import get_firestore_client
                client = get_firestore_client()
                if client is not None:
                    doc = client.collection("intelligence_conversations").document(f"conv_{conversation_id}").get()
                    if doc.exists:
                        data = doc.to_dict() or {}
                        if data.get("user_id") != user_id:
                            return False, f"Access denied: Conversation {conversation_id} belongs to a different user."
                        if data.get("portal_type") == "company" and data.get("company_id") and data.get("company_id") != company_id:
                            return False, f"Access denied: Conversation {conversation_id} belongs to a different company organization."
            except Exception:
                pass
            return True, None

        if state.user_id != user_id:
            return False, f"Access denied: Conversation {conversation_id} belongs to a different user."

        if state.portal_type == "company" and state.company_id and state.company_id != company_id:
            return False, f"Access denied: Conversation {conversation_id} belongs to a different company organization."

        return True, None

    def save_turn(
        self,
        *,
        conversation_id: str,
        user_id: str,
        company_id: str | None = None,
        portal_type: str = "individual",
        domain: str | None = None,
        user_message: str,
        intent: str,
        primary_entity: str | None = None,
        resolved_entities: list[str] | None = None,
        comparison_entities: list[str] | None = None,
        target_role: str | None = None,
        time_range: str = "30d",
        selected_skills: list[str] | None = None,
        selected_companies: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        execution_status: str = "completed",
        answer_summary: str | None = None,
        client_message_id: str | None = None,
        response_payload: dict[str, Any] | None = None,
        regenerate_existing: bool = False,
    ) -> ConversationState:
        """Record an executed turn into the conversation session (idempotent on client_message_id)."""
        now = datetime.now(timezone.utc)

        if regenerate_existing:
            with self._access_lock:
                state_loaded = conversation_id in self._conversations
            if not state_loaded:
                self.get_conversation(conversation_id, user_id=user_id, company_id=company_id)

        with self._access_lock:
            state = self._conversations.get(conversation_id)
            existing_turn = None
            if state is not None:
                if state.user_id != user_id:
                    raise PermissionError(f"User {user_id} does not own conversation {conversation_id}.")
                if state.portal_type == "company" and state.company_id and state.company_id != company_id:
                    raise PermissionError(f"Company {company_id} does not own conversation {conversation_id}.")
                if client_message_id:
                    existing_turn = next(
                        (turn for turn in state.turns if turn.client_message_id == client_message_id),
                        None,
                    )
                    if existing_turn and not regenerate_existing:
                        return state

            turn = ConversationTurn(
                turn_id=existing_turn.turn_id if existing_turn else f"turn_{now.strftime('%Y%m%d%H%M%S')}_{len(user_message)}",
                client_message_id=client_message_id,
                user_message=user_message,
                intent=intent,
                domain=domain,
                primary_entity=primary_entity,
                resolved_entities=resolved_entities or [],
                comparison_entities=comparison_entities or [],
                target_role=target_role,
                time_range=time_range,
                selected_skills=selected_skills or [],
                selected_companies=selected_companies or [],
                filters=dict(filters or {}),
                execution_status=execution_status,
                answer_summary=answer_summary,
                response_payload=response_payload,
                timestamp=now,
            )

            if state is None:
                state = ConversationState(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    company_id=company_id,
                    portal_type=portal_type,
                    domain=domain,
                    title=user_message[:60] if user_message else "New Conversation",
                    active_entity=primary_entity,
                    comparison_entities=comparison_entities or [],
                    active_role=target_role,
                    time_range=time_range,
                    selected_skills=selected_skills or [],
                    selected_companies=selected_companies or [],
                    filters=dict(filters or {}),
                    turns=[turn],
                    created_at=now,
                    updated_at=now,
                )
            else:
                if existing_turn:
                    turn_index = state.turns.index(existing_turn)
                    state.turns[turn_index] = turn
                else:
                    state.turns.append(turn)
                if not state.title or state.title == "New Conversation":
                    state.title = user_message[:60]
                if domain:
                    state.domain = domain
                if primary_entity:
                    state.active_entity = primary_entity
                if comparison_entities:
                    state.comparison_entities = comparison_entities
                if target_role:
                    state.active_role = target_role
                if selected_skills:
                    state.selected_skills = list(set(state.selected_skills + selected_skills))
                if selected_companies:
                    state.selected_companies = list(set(state.selected_companies + selected_companies))
                if filters:
                    state.filters = dict(filters)
                state.time_range = time_range
                state.updated_at = now

            self._conversations[conversation_id] = state

        # Persist document to Firestore when available
        try:
            from app.core.firebase import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                client.collection("intelligence_conversations").document(f"conv_{conversation_id}").set(
                    state.model_dump(mode="json"),
                    merge=True,
                )
        except Exception as exc:
            logger.debug("Firestore conversation save safely skipped: %s", exc)

        return state

    def list_conversations(
        self,
        *,
        user_id: str,
        company_id: str | None = None,
        domain: str | None = None,
        portal_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List active conversation summaries belonging to the user."""
        conversations: list[dict[str, Any]] = []
        with self._access_lock:
            for conv_id, state in self._conversations.items():
                if state.user_id == user_id:
                    if state.portal_type == "company" and state.company_id and state.company_id != company_id:
                        continue
                    if portal_type and state.portal_type != portal_type:
                        continue
                    if domain and (state.domain or "skill") != domain:
                        continue
                    first_turn = state.turns[0] if state.turns else None
                    title = (
                        state.title
                        or (first_turn.user_message[:60] if first_turn else None)
                        or (f"Analysis for {state.active_entity}" if state.active_entity else "New Conversation")
                    )
                    conversations.append({
                        "conversation_id": conv_id,
                        "title": title,
                        "domain": state.domain or "skill",
                        "filters": state.filters or {},
                        "active_entity": state.active_entity,
                        "portal_type": state.portal_type,
                        "turn_count": len(state.turns),
                        "created_at": state.created_at.isoformat(),
                        "updated_at": state.updated_at.isoformat(),
                    })

        # Also merge from Firestore if available
        try:
            from app.core.firebase import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                query = client.collection("intelligence_conversations").where("user_id", "==", user_id)
                docs = list(query.stream())
                known_ids = {c["conversation_id"] for c in conversations}
                for doc in docs:
                    data = doc.to_dict() or {}
                    cid = data.get("conversation_id")
                    if cid and cid not in known_ids:
                        if data.get("portal_type") == "company" and data.get("company_id") and data.get("company_id") != company_id:
                            continue
                        if portal_type and data.get("portal_type", "individual") != portal_type:
                            continue
                        doc_domain = data.get("domain") or "skill"
                        if domain and doc_domain != domain:
                            continue
                        turns = data.get("turns", [])
                        first_msg = turns[0].get("user_message", "") if turns else ""
                        title = data.get("title") or (first_msg[:60] if first_msg else f"Analysis for {data.get('active_entity', 'Session')}")
                        conversations.append({
                            "conversation_id": cid,
                            "title": title,
                            "domain": doc_domain or "skill",
                            "filters": data.get("filters") or {},
                            "active_entity": data.get("active_entity"),
                            "portal_type": data.get("portal_type", "individual"),
                            "turn_count": len(turns),
                            "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
                            "updated_at": data.get("updated_at", datetime.now(timezone.utc).isoformat()),
                        })
        except Exception as exc:
            logger.debug("Firestore list_conversations safely skipped: %s", exc)

        conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return conversations[:limit]

    def delete_conversation(
        self,
        conversation_id: str,
        *,
        user_id: str,
        company_id: str | None = None,
        domain: str | None = None,
        portal_type: str | None = None,
    ) -> bool:
        """Permanently delete conversation state for the given user and company."""
        deleted = False
        with self._access_lock:
            state = self._conversations.get(conversation_id)
            if state is not None:
                if state.user_id != user_id:
                    raise PermissionError(f"User {user_id} does not own conversation {conversation_id}.")
                if state.portal_type == "company" and state.company_id and state.company_id != company_id:
                    raise PermissionError(f"Company {company_id} does not own conversation {conversation_id}.")
                if (portal_type and state.portal_type != portal_type) or (domain and (state.domain or "skill") != domain):
                    return False
                del self._conversations[conversation_id]
                deleted = True

        try:
            from app.core.firebase import get_firestore_client
            client = get_firestore_client()
            if client is not None:
                doc_ref = client.collection("intelligence_conversations").document(f"conv_{conversation_id}")
                if deleted:
                    doc_ref.delete()
                else:
                    doc = doc_ref.get()
                    if doc.exists:
                        doc_data = doc.to_dict() or {}
                        if doc_data.get("user_id") != user_id:
                            raise PermissionError(f"User {user_id} does not own conversation {conversation_id}.")
                        if doc_data.get("portal_type") == "company" and doc_data.get("company_id") and doc_data.get("company_id") != company_id:
                            raise PermissionError(f"Company {company_id} does not own conversation {conversation_id}.")
                        if portal_type and doc_data.get("portal_type", "individual") != portal_type:
                            return False
                        if domain and (doc_data.get("domain") or "skill") != domain:
                            return False
                        doc_ref.delete()
                        deleted = True
        except PermissionError:
            raise
        except Exception as exc:
            logger.debug("Firestore delete_conversation safely skipped: %s", exc)

        return deleted

    def clear_conversation(self, conversation_id: str, *, user_id: str, company_id: str | None = None) -> bool:
        """Explicitly clear conversation state for the given user."""
        return self.delete_conversation(conversation_id, user_id=user_id, company_id=company_id)

    def resolve_follow_up(
        self,
        message: str,
        conversation_id: str | None,
        *,
        user_id: str,
        company_id: str | None = None,
    ) -> tuple[str | None, list[str], str | None, str | None]:
        """Resolve pronouns or missing entity context using prior conversation turns.

        Returns: (resolved_primary_entity, comparison_entities, active_role, resolved_message)
        """
        if not conversation_id:
            return None, [], None, None

        state = self.get_conversation(conversation_id, user_id=user_id, company_id=company_id)
        if state is None or not state.active_entity:
            return None, [], None, None

        has_pronoun = bool(PRONOUN_PATTERN.search(message))
        resolved_primary = state.active_entity
        comparison_entities = state.comparison_entities
        active_role = state.active_role

        if re.fullmatch(r"\s*(?:why|how so|why is that|why so)[?.!]*\s*", message, re.IGNORECASE):
            prior_query = next(
                (
                    turn.user_message
                    for turn in reversed(state.turns)
                    if turn.user_message.strip()
                    and not re.fullmatch(
                        r"\s*(?:why|how so|why is that|why so)[?.!]*\s*",
                        turn.user_message,
                        re.IGNORECASE,
                    )
                ),
                None,
            )
            if prior_query:
                return resolved_primary, comparison_entities, active_role, prior_query

        # If message explicitly says "Compare it with Java" or similar
        comp_match = re.search(r"\bcompare\s+(it|this|that)\s+(?:with|to|and|vs|versus)\s+([A-Za-z0-9\.\+#]+)", message, re.IGNORECASE)
        if comp_match:
            other_entity = comp_match.group(2).strip()
            return resolved_primary, [other_entity], active_role, f"Compare {resolved_primary} and {other_entity}"

        return resolved_primary, comparison_entities, active_role, None
