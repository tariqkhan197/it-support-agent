"""
Screenshot Diagnosis (OCR) — upload a screenshot of an error dialog or
blue screen and get automatic text extraction, error-code recognition,
and a full diagnosis. Employee-facing, no login required.
"""

import streamlit as st

from utils import APIError, api_upload, init_session_state, inject_custom_css, render_app_header

st.set_page_config(page_title="Screenshot Diagnosis — IT Support Agent", page_icon="🖼️", layout="wide")
inject_custom_css()
init_session_state()

with st.sidebar:
    st.markdown("## 🛠️ IT Help Desk")
    st.caption("Screenshot Diagnosis")

render_app_header("🖼️ Screenshot Diagnosis", "Upload a screenshot of an error message or blue screen — I'll read it and diagnose the issue")

uploaded_image = st.file_uploader("Choose a screenshot", type=["png", "jpg", "jpeg", "bmp", "webp"])
extra_context = st.text_area("Any extra details? (optional)", placeholder="e.g. This started after I installed a Windows update...")

if uploaded_image is not None:
    st.image(uploaded_image, caption=uploaded_image.name, use_container_width=True)

if st.button("🔍 Analyze Screenshot", type="primary", disabled=uploaded_image is None):
    with st.spinner("Reading the screenshot and diagnosing the issue..."):
        try:
            result = api_upload(
                "/ocr/analyze",
                file_bytes=uploaded_image.getvalue(),
                filename=uploaded_image.name,
                form_data={"user_message": extra_context} if extra_context else None,
                auth=False,
            )

            st.success(f"Routed to: **{result['routed_category'].title()} Agent**")

            with st.expander("📝 Extracted text", expanded=False):
                st.code(result["raw_extracted_text"])

            if result["detected_error_codes"]:
                st.markdown("#### 🔎 Detected error codes")
                for code in result["detected_error_codes"]:
                    st.markdown(f"**`{code['code']}`** ({code['code_type'].replace('_', ' ')})")
                    if code.get("known_description"):
                        st.write(code["known_description"])
                    if code.get("known_causes"):
                        st.write("Known causes: " + ", ".join(code["known_causes"]))
                    st.markdown("---")

            diagnosis = result["diagnosis"]
            st.markdown("#### 🩺 Diagnosis")
            st.write(diagnosis["analysis"])

            st.markdown("**Possible causes:**")
            for cause in diagnosis["possible_causes"]:
                st.markdown(f"- {cause}")

            if diagnosis.get("solution_steps"):
                st.markdown("**Steps to try:**")
                for i, step in enumerate(diagnosis["solution_steps"], start=1):
                    st.markdown(f"{i}. {step}")

            if diagnosis.get("follow_up_question"):
                st.info(f"❓ {diagnosis['follow_up_question']}")

            if diagnosis.get("requires_ticket"):
                st.warning(
                    "This issue likely needs an engineer. Go to the Chat page and describe it "
                    "there to automatically open a support ticket."
                )

        except APIError as exc:
            st.error(f"Analysis failed: {exc.message}")
