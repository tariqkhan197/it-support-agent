"""
Knowledge Base Management — upload PDFs into the RAG system, view
indexed documents, and delete them. Login-protected (admin JWT).
"""

import streamlit as st

from utils import (
    APIError,
    admin_logout_button,
    api_delete,
    api_get,
    api_upload,
    init_session_state,
    inject_custom_css,
    render_app_header,
    require_admin_login,
)

st.set_page_config(page_title="Knowledge Base — IT Support Agent", page_icon="📚", layout="wide")
inject_custom_css()
init_session_state()

with st.sidebar:
    st.markdown("## 🛠️ IT Help Desk")
    st.caption("Knowledge Base")
    admin_logout_button()

if not require_admin_login():
    st.stop()

render_app_header("📚 Knowledge Base", "Upload company IT documentation so the assistant can ground its answers in it")

# ---------------------------------------------------------------- #
# Upload
# ---------------------------------------------------------------- #
st.markdown("#### Upload a document")
with st.form("upload_form", clear_on_submit=True):
    uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
    category = st.selectbox(
        "Category (optional)",
        ["", "windows", "networking", "printer", "vpn", "email", "security", "general"],
    )
    submitted = st.form_submit_button("Upload & Index")

if submitted:
    if uploaded_file is None:
        st.warning("Please choose a PDF file first.")
    else:
        with st.spinner(f"Processing '{uploaded_file.name}' — extracting, chunking, and embedding..."):
            try:
                doc = api_upload(
                    "/knowledge/upload",
                    file_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    form_data={"category": category} if category else None,
                    auth=True,
                )
                st.success(
                    f"✅ Indexed '{doc['original_filename']}' — "
                    f"{doc['page_count']} pages, {doc['chunk_count']} chunks."
                )
                st.rerun()
            except APIError as exc:
                st.error(f"Upload failed: {exc.message}")

st.divider()

# ---------------------------------------------------------------- #
# Document list
# ---------------------------------------------------------------- #
st.markdown("#### Indexed documents")
try:
    documents = api_get("/knowledge/documents", auth=True)
except APIError as exc:
    st.error(f"Failed to load documents: {exc.message}")
    st.stop()

if not documents:
    st.info("No documents uploaded yet. Add IT policies, manuals, or SOPs above so the assistant can reference them.")
else:
    for doc in documents:
        cols = st.columns([3, 1, 1, 1, 1])
        cols[0].markdown(f"**📄 {doc['original_filename']}**  \n<span style='color:#9aa4b2;font-size:0.82rem;'>{doc.get('category') or 'Uncategorized'} · uploaded {doc['uploaded_at'][:10]}</span>", unsafe_allow_html=True)
        cols[1].metric("Pages", doc["page_count"])
        cols[2].metric("Chunks", doc["chunk_count"])
        cols[3].metric("Size", f"{doc['file_size_bytes'] / 1024:.0f} KB")
        with cols[4]:
            st.write("")
            if st.button("🗑️ Delete", key=f"del_doc_{doc['id']}", use_container_width=True):
                try:
                    api_delete(f"/knowledge/documents/{doc['id']}", auth=True)
                    st.success("Deleted.")
                    st.rerun()
                except APIError as exc:
                    st.error(exc.message)
        st.divider()
