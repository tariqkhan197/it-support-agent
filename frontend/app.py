"""
AI IT Support Agent — Chat Interface (Home page).

Employee-facing chat: type an IT issue, get routed to the right specialist
agent, receive step-by-step troubleshooting, and get a ticket automatically
if the issue needs an engineer.
"""

import uuid

import streamlit as st

from utils import (
    API_BASE_URL,
    APIError,
    CATEGORY_LABELS,
    api_post,
    init_session_state,
    inject_custom_css,
    render_app_header,
)

st.set_page_config(
    page_title="AI IT Support Agent",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()
init_session_state()

if not st.session_state.get("user_identifier"):
    st.session_state.user_identifier = f"guest-{uuid.uuid4().hex[:8]}"

# ---------------------------------------------------------------- #
# Sidebar
# ---------------------------------------------------------------- #
with st.sidebar:
    st.markdown("## 🛠️ IT Help Desk")
    st.caption("AI-powered support assistant")
    st.divider()

    st.markdown("**Your session**")
    identifier_input = st.text_input(
        "Your email (optional, for ticket follow-up)",
        value="" if st.session_state.user_identifier.startswith("guest-") else st.session_state.user_identifier,
        placeholder="you@company.com",
    )
    if identifier_input:
        st.session_state.user_identifier = identifier_input

    st.divider()
    if st.button("🔄 Start New Conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

    st.divider()
    st.caption("Need to check a ticket, upload documentation, or diagnose a screenshot? Use the pages in the sidebar above.")

# ---------------------------------------------------------------- #
# Main chat area
# ---------------------------------------------------------------- #
render_app_header("💬 AI IT Support Assistant", "Describe your issue in plain language — I'll diagnose it and walk you through the fix.")

if not st.session_state.chat_history:
    st.markdown(
        """
        <div class="itsa-card">
        <b>Try asking about:</b><br>
        "My laptop is really slow" &nbsp;•&nbsp;
        "Printer not working" &nbsp;•&nbsp;
        "VPN not connecting" &nbsp;•&nbsp;
        "Outlook won't open" &nbsp;•&nbsp;
        "I forgot my password" &nbsp;•&nbsp;
        "Blue screen error"
        </div>
        """,
        unsafe_allow_html=True,
    )

# Render chat history
for turn in st.session_state.chat_history:
    if turn["role"] == "user":
        st.markdown(f'<div class="itsa-chat-user">{turn["content"]}</div>', unsafe_allow_html=True)
    else:
        agent_label = CATEGORY_LABELS.get(turn.get("meta", {}).get("category", ""), "")
        label_html = f'<div class="itsa-chat-agent-label">{agent_label} Agent</div>' if agent_label else ""
        st.markdown(
            f'<div class="itsa-chat-assistant">{label_html}{turn["content"]}</div>',
            unsafe_allow_html=True,
        )
        meta = turn.get("meta", {})
        if meta.get("ticket_number"):
            st.info(f"🎫 A support ticket was created: **{meta['ticket_number']}** — an engineer will follow up.")
        if meta.get("sources"):
            chips = "".join(
                f'<span class="itsa-source-chip">📄 {s["filename"]} (p.{s["page"]})</span>'
                for s in meta["sources"]
            )
            st.markdown(f"<div style='margin-bottom:1rem;'>{chips}</div>", unsafe_allow_html=True)

# Chat input
user_message = st.chat_input("Describe your IT issue...")

if user_message:
    st.session_state.chat_history.append({"role": "user", "content": user_message})

    with st.spinner("Diagnosing your issue..."):
        try:
            response = api_post(
                "/chat",
                json_body={
                    "user_identifier": st.session_state.user_identifier,
                    "message": user_message,
                },
            )
            diagnosis = response["diagnosis"]

            lines = [diagnosis["analysis"]]
            if diagnosis.get("solution_steps"):
                lines.append("<br><b>Steps to try:</b><ol>")
                lines.extend(f"<li>{step}</li>" for step in diagnosis["solution_steps"])
                lines.append("</ol>")
            if diagnosis.get("follow_up_question"):
                lines.append(f"<br>❓ {diagnosis['follow_up_question']}")

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": "".join(lines),
                "meta": {
                    "category": response.get("category"),
                    "ticket_number": response.get("ticket_number"),
                    "sources": response.get("retrieved_sources", []),
                },
            })
        except APIError as exc:
            error_text = (
                "I couldn't reach the AI backend right now. "
                f"({exc.message})"
            )
            st.session_state.chat_history.append({"role": "assistant", "content": error_text})
        except Exception as exc:  # noqa: BLE001
            st.session_state.chat_history.append(
                {"role": "assistant", "content": f"Something went wrong: {exc}"}
            )

    st.rerun()
