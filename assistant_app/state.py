import os
from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class AppStatus:
    api_key_configured: bool
    vault_path_exists: bool
    vault_document_count: int
    active_mode: str
    upload_ready: bool
    chat_ready: bool
    startup_error: str | None


def ensure_session_state(chat_modes: tuple[str, str]) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_mode" not in st.session_state:
        st.session_state.last_mode = chat_modes[0]


def maybe_reset_chat_for_mode(app_mode: str) -> None:
    if st.session_state.last_mode != app_mode:
        st.session_state.messages = []
        st.session_state.last_mode = app_mode


def clear_chat_history() -> None:
    st.session_state.messages = []


def build_status(vault_path: str, api_key: str, app_mode: str, uploaded_file, vault_document_count: int) -> AppStatus:
    return AppStatus(
        api_key_configured=bool(api_key),
        vault_path_exists=bool(vault_path) and os.path.isdir(vault_path),
        vault_document_count=vault_document_count,
        active_mode=app_mode,
        upload_ready=uploaded_file is not None,
        chat_ready=False,
        startup_error=None,
    )


def with_status(status: AppStatus, **changes) -> AppStatus:
    values = {
        "api_key_configured": status.api_key_configured,
        "vault_path_exists": status.vault_path_exists,
        "vault_document_count": status.vault_document_count,
        "active_mode": status.active_mode,
        "upload_ready": status.upload_ready,
        "chat_ready": status.chat_ready,
        "startup_error": status.startup_error,
    }
    values.update(changes)
    return AppStatus(**values)


def get_chat_readiness(app_mode: str, vault_index, uploaded_file) -> tuple[bool, str | None]:
    if vault_index is None:
        return False, "Chatten er deaktiveret, indtil vault-indekset er klar."
    if app_mode == "Case Analyse (Audit)" and uploaded_file is None:
        return False, "Upload en kundecase for at aktivere audit-chatten."
    return True, None

