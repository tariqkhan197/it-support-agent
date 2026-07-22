"""
Frontend utilities: API client + shared UI helpers.

Kept separate from the page files so every Streamlit page shares the same
HTTP client behavior, error handling, and visual components (badges,
cards, CSS injection) — no duplicated logic across pages.
"""

import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
_CSS_PATH = Path(__file__).parent / "assets" / "css" / "theme.css"

STATUS_LABELS = {"open": "Open", "in_progress": "In Progress", "resolved": "Resolved", "closed": "Closed", "reopened": "Reopened"}
PRIORITY_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
CATEGORY_LABELS = {
    "windows": "Windows", "networking": "Networking", "printer": "Printer",
    "vpn": "VPN", "email": "Email", "security": "Security", "general": "General",
}


# ---------------------------------------------------------------- #
# Page setup / styling
# ---------------------------------------------------------------- #
def inject_custom_css() -> None:
    """Load and inject the shared dark-theme stylesheet. Call once per page."""
    if _CSS_PATH.exists():
        st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)


def render_app_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div style="margin-bottom: 1.25rem;">
            <p class="itsa-app-title">{title}</p>
            <p class="itsa-app-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_badge_html(status: str) -> str:
    label = STATUS_LABELS.get(status, status)
    return f'<span class="itsa-badge itsa-badge-{status}">{label}</span>'


def priority_badge_html(priority: str) -> str:
    label = PRIORITY_LABELS.get(priority, priority)
    return f'<span class="itsa-badge itsa-badge-{priority}">{label}</span>'


def metric_card(label: str, value: Any) -> str:
    return f"""
        <div class="itsa-metric-card">
            <div class="itsa-metric-value">{value}</div>
            <div class="itsa-metric-label">{label}</div>
        </div>
    """


# ---------------------------------------------------------------- #
# Session state
# ---------------------------------------------------------------- #
def init_session_state() -> None:
    defaults = {
        "admin_token": None,
        "admin_username": None,
        "user_identifier": None,
        "chat_history": [],  # list of {"role": ..., "content": ..., "meta": {...}}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_admin_logged_in() -> bool:
    return st.session_state.get("admin_token") is not None


def require_admin_login() -> bool:
    """
    Renders a login form if the admin isn't authenticated yet.
    Returns True if already logged in (page should render its content),
    False if the login form was shown instead (page should stop).
    """
    init_session_state()
    if is_admin_logged_in():
        return True

    st.markdown("### 🔒 Admin Login Required")
    with st.form("admin_login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In")

    if submitted:
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                st.session_state.admin_token = data["access_token"]
                st.session_state.admin_username = username
                st.success("Logged in successfully.")
                st.rerun()
            else:
                st.error(response.json().get("message", "Login failed."))
        except requests.RequestException as exc:
            st.error(f"Could not reach the API server: {exc}")

    return False


def admin_logout_button() -> None:
    if is_admin_logged_in() and st.sidebar.button("Log Out", use_container_width=True):
        st.session_state.admin_token = None
        st.session_state.admin_username = None
        st.rerun()


# ---------------------------------------------------------------- #
# API client
# ---------------------------------------------------------------- #
class APIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _auth_headers() -> dict:
    token = st.session_state.get("admin_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle_response(response: requests.Response) -> Any:
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise APIError(detail, status_code=response.status_code)
    if response.content:
        return response.json()
    return None


def api_get(path: str, params: dict | None = None, auth: bool = False) -> Any:
    headers = _auth_headers() if auth else {}
    response = requests.get(f"{API_BASE_URL}{path}", params=params, headers=headers, timeout=30)
    return _handle_response(response)


def api_post(path: str, json_body: dict | None = None, params: dict | None = None, auth: bool = False) -> Any:
    headers = _auth_headers() if auth else {}
    response = requests.post(f"{API_BASE_URL}{path}", json=json_body, params=params, headers=headers, timeout=60)
    return _handle_response(response)


def api_patch(path: str, json_body: dict, auth: bool = True) -> Any:
    headers = _auth_headers() if auth else {}
    response = requests.patch(f"{API_BASE_URL}{path}", json=json_body, headers=headers, timeout=30)
    return _handle_response(response)


def api_delete(path: str, auth: bool = True) -> Any:
    headers = _auth_headers() if auth else {}
    response = requests.delete(f"{API_BASE_URL}{path}", headers=headers, timeout=30)
    return _handle_response(response)


def api_upload(path: str, file_bytes: bytes, filename: str, form_data: dict | None = None, auth: bool = True) -> Any:
    headers = _auth_headers() if auth else {}
    files = {"file": (filename, file_bytes)}
    response = requests.post(
        f"{API_BASE_URL}{path}", files=files, data=form_data or {}, headers=headers, timeout=120
    )
    return _handle_response(response)


def api_get_raw(path: str, auth: bool = True) -> requests.Response:
    """For endpoints returning raw content (e.g. CSV export) rather than JSON."""
    headers = _auth_headers() if auth else {}
    response = requests.get(f"{API_BASE_URL}{path}", headers=headers, timeout=30)
    if response.status_code >= 400:
        raise APIError(response.text, status_code=response.status_code)
    return response
