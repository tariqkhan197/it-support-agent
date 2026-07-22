"""
Admin Dashboard — ticket analytics, charts, and weekly overview.
Login-protected (admin JWT).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import (
    APIError,
    CATEGORY_LABELS,
    STATUS_LABELS,
    admin_logout_button,
    api_get,
    init_session_state,
    inject_custom_css,
    metric_card,
    render_app_header,
    require_admin_login,
)

st.set_page_config(page_title="Dashboard — IT Support Agent", page_icon="📊", layout="wide")
inject_custom_css()
init_session_state()

with st.sidebar:
    st.markdown("## 🛠️ IT Help Desk")
    st.caption("Admin Dashboard")
    admin_logout_button()

if not require_admin_login():
    st.stop()

render_app_header("📊 Admin Dashboard", "Live ticket analytics and system overview")

try:
    analytics = api_get("/tickets/analytics", auth=True)
except APIError as exc:
    st.error(f"Failed to load analytics: {exc.message}")
    st.stop()

# ---------------------------------------------------------------- #
# Metric cards
# ---------------------------------------------------------------- #
cols = st.columns(5)
metrics = [
    ("Total Tickets", analytics["total_tickets"]),
    ("Open", analytics["open_tickets"]),
    ("Closed", analytics["closed_tickets"]),
    ("Critical", analytics["critical_tickets"]),
    ("Created Today", analytics["tickets_created_today"]),
]
for col, (label, value) in zip(cols, metrics):
    with col:
        st.markdown(metric_card(label, value), unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

avg_resolution = analytics.get("average_resolution_time_hours")
st.markdown(
    metric_card(
        "Average Resolution Time",
        f"{avg_resolution:.1f} hrs" if avg_resolution is not None else "No resolved tickets yet",
    ),
    unsafe_allow_html=True,
)

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------- #
# Charts
# ---------------------------------------------------------------- #
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### Tickets by Status")
    status_data = analytics.get("tickets_by_status", {})
    if status_data:
        labels = [STATUS_LABELS.get(k, k) for k in status_data.keys()]
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=list(status_data.values()),
            hole=0.55,
            marker=dict(colors=["#4f8bff", "#eab308", "#22c55e", "#9aa4b2", "#f97316"]),
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e8eaed",
            margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ticket data yet.")

with chart_col2:
    st.markdown("#### Tickets by Category")
    category_data = analytics.get("tickets_by_category", {})
    if category_data:
        labels = [CATEGORY_LABELS.get(k, k) for k in category_data.keys()]
        fig = go.Figure(data=[go.Bar(
            x=labels,
            y=list(category_data.values()),
            marker_color="#4f8bff",
        )])
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e8eaed",
            margin=dict(t=10, b=10, l=10, r=10),
            xaxis=dict(gridcolor="#2a3244"),
            yaxis=dict(gridcolor="#2a3244"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No ticket data yet.")

st.divider()
st.caption("Data refreshes each time this page loads. Use the Tickets page to manage individual tickets.")
