"""
Ticket Management — search/filter, view details, edit, assign, change
status, and export. Login-protected (admin JWT).
"""

import streamlit as st

from utils import (
    APIError,
    CATEGORY_LABELS,
    PRIORITY_LABELS,
    STATUS_LABELS,
    admin_logout_button,
    api_get,
    api_get_raw,
    api_patch,
    api_post,
    init_session_state,
    inject_custom_css,
    priority_badge_html,
    render_app_header,
    require_admin_login,
    status_badge_html,
)

st.set_page_config(page_title="Tickets — IT Support Agent", page_icon="🎫", layout="wide")
inject_custom_css()
init_session_state()

with st.sidebar:
    st.markdown("## 🛠️ IT Help Desk")
    st.caption("Ticket Management")
    admin_logout_button()

if not require_admin_login():
    st.stop()

render_app_header("🎫 Ticket Management", "Search, triage, assign, and resolve support tickets")

# ---------------------------------------------------------------- #
# Filters
# ---------------------------------------------------------------- #
filter_cols = st.columns([2, 1, 1, 1, 1])
with filter_cols[0]:
    search_text = st.text_input("Search", placeholder="Search title, description, requester, ticket #...")
with filter_cols[1]:
    status_filter = st.selectbox("Status", ["All"] + list(STATUS_LABELS.keys()), format_func=lambda x: STATUS_LABELS.get(x, x))
with filter_cols[2]:
    category_filter = st.selectbox("Category", ["All"] + list(CATEGORY_LABELS.keys()), format_func=lambda x: CATEGORY_LABELS.get(x, x))
with filter_cols[3]:
    priority_filter = st.selectbox("Priority", ["All"] + list(PRIORITY_LABELS.keys()), format_func=lambda x: PRIORITY_LABELS.get(x, x))
with filter_cols[4]:
    st.write("")
    st.write("")
    if st.button("⬇️ Export CSV", use_container_width=True):
        try:
            csv_response = api_get_raw("/tickets/export", auth=True)
            st.download_button(
                "Download CSV file", data=csv_response.content,
                file_name="tickets_export.csv", mime="text/csv",
            )
        except APIError as exc:
            st.error(f"Export failed: {exc.message}")

params = {"limit": 100}
if search_text:
    params["search_text"] = search_text
if status_filter != "All":
    params["status"] = status_filter
if category_filter != "All":
    params["category"] = category_filter
if priority_filter != "All":
    params["priority"] = priority_filter

try:
    result = api_get("/tickets", params=params)
    tickets = result["tickets"]
    total = result["total"]
except APIError as exc:
    st.error(f"Failed to load tickets: {exc.message}")
    st.stop()

st.caption(f"Showing {len(tickets)} of {total} matching tickets")

if not tickets:
    st.info("No tickets match the current filters.")
    st.stop()

# ---------------------------------------------------------------- #
# Ticket list + detail editor
# ---------------------------------------------------------------- #
for ticket in tickets:
    header = (
        f"**{ticket['ticket_number']}** — {ticket['title']}  "
        f"&nbsp;&nbsp;{status_badge_html(ticket['status'])} {priority_badge_html(ticket['priority'])}"
    )
    with st.expander(header):
        st.markdown(header, unsafe_allow_html=True)
        st.write(ticket["description"])

        detail_cols = st.columns(3)
        detail_cols[0].markdown(f"**Requester:** {ticket['requester_name']}")
        detail_cols[1].markdown(f"**Category:** {CATEGORY_LABELS.get(ticket['category'], ticket['category'])}")
        detail_cols[2].markdown(f"**Assigned:** {ticket['assigned_engineer'] or '_Unassigned_'}")

        st.caption(f"Created: {ticket['created_at']}  |  Updated: {ticket['updated_at']}")
        if ticket.get("resolution_notes"):
            st.markdown(f"**Resolution notes:** {ticket['resolution_notes']}")

        st.divider()
        action_cols = st.columns(4)

        with action_cols[0]:
            engineer_name = st.text_input("Assign to", key=f"assign_{ticket['id']}", placeholder="Engineer name")
            if st.button("Assign", key=f"assign_btn_{ticket['id']}", use_container_width=True):
                if engineer_name:
                    try:
                        api_post(f"/tickets/{ticket['id']}/assign", params={"engineer_name": engineer_name}, auth=True)
                        st.success("Assigned.")
                        st.rerun()
                    except APIError as exc:
                        st.error(exc.message)
                else:
                    st.warning("Enter an engineer name first.")

        with action_cols[1]:
            new_status = st.selectbox(
                "Change status", list(STATUS_LABELS.keys()),
                index=list(STATUS_LABELS.keys()).index(ticket["status"]),
                format_func=lambda x: STATUS_LABELS.get(x, x),
                key=f"status_{ticket['id']}",
            )
            resolution_note = st.text_input("Note (optional)", key=f"note_{ticket['id']}")
            if st.button("Update Status", key=f"status_btn_{ticket['id']}", use_container_width=True):
                try:
                    api_post(
                        f"/tickets/{ticket['id']}/status",
                        json_body={
                            "new_status": new_status,
                            "resolution_notes": resolution_note or None,
                            "changed_by": st.session_state.get("admin_username", "admin"),
                        },
                        auth=True,
                    )
                    st.success("Status updated.")
                    st.rerun()
                except APIError as exc:
                    st.error(exc.message)

        with action_cols[2]:
            new_priority = st.selectbox(
                "Change priority", list(PRIORITY_LABELS.keys()),
                index=list(PRIORITY_LABELS.keys()).index(ticket["priority"]),
                format_func=lambda x: PRIORITY_LABELS.get(x, x),
                key=f"priority_{ticket['id']}",
            )
            if st.button("Update Priority", key=f"priority_btn_{ticket['id']}", use_container_width=True):
                try:
                    api_patch(f"/tickets/{ticket['id']}", {"priority": new_priority}, auth=True)
                    st.success("Priority updated.")
                    st.rerun()
                except APIError as exc:
                    st.error(exc.message)

        with action_cols[3]:
            st.write("")
            if st.button("🗑️ Delete Ticket", key=f"delete_{ticket['id']}", use_container_width=True):
                st.session_state[f"confirm_delete_{ticket['id']}"] = True

            if st.session_state.get(f"confirm_delete_{ticket['id']}"):
                st.warning("Are you sure? This cannot be undone.")
                confirm_cols = st.columns(2)
                if confirm_cols[0].button("Yes, delete", key=f"confirm_yes_{ticket['id']}"):
                    from utils import api_delete
                    try:
                        api_delete(f"/tickets/{ticket['id']}", auth=True)
                        st.success("Deleted.")
                        del st.session_state[f"confirm_delete_{ticket['id']}"]
                        st.rerun()
                    except APIError as exc:
                        st.error(exc.message)
                if confirm_cols[1].button("Cancel", key=f"confirm_no_{ticket['id']}"):
                    del st.session_state[f"confirm_delete_{ticket['id']}"]
                    st.rerun()
