import logging

import streamlit as st

from assistant_app.config import (
    CHAT_MODES,
    LOG_FILE,
    SUPPORTED_UPLOAD_TYPES,
    VOKSEWERK_GREEN,
    VOKSEWERK_NAVY,
    AppConfig,
    configure_logging,
    load_config,
)
from assistant_app.audit import run_case_audit
from assistant_app.startup import initialize_app
from assistant_app.state import (
    AppStatus,
    build_status,
    clear_chat_history,
    ensure_session_state,
    get_chat_readiness,
    maybe_reset_chat_for_mode,
    with_status,
)
from assistant_app.validation import validate_prompt
from assistant_app.vault import run_strategic_query


LOGGER = logging.getLogger(__name__)


@st.cache_resource(show_spinner="Indlaeser Obsidian Vault...")
def load_cached_vault_index(vault_path: str, api_key: str, groq_model: str, embed_model: str):
    from assistant_app.vault import build_vault_index

    return build_vault_index(vault_path, api_key, groq_model, embed_model)


def render_branding() -> None:
    st.set_page_config(page_title="Voksewerk Strategisk Assistent", layout="wide")
    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: white; }}
        .main-header {{
            color: {VOKSEWERK_NAVY};
            font-family: 'Helvetica', sans-serif;
            border-bottom: 4px solid {VOKSEWERK_GREEN};
            padding-bottom: 5px;
            margin-bottom: 20px;
        }}
        [data-testid="stSidebar"] {{ background-color: {VOKSEWERK_NAVY} !important; }}
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] label {{ color: white !important; }}
        div[data-baseweb="select"] > div {{
            background-color: rgba(255,255,255,0.1);
            color: white !important;
        }}
        div.stButton > button {{
            background-color: {VOKSEWERK_GREEN} !important;
            color: white !important;
            width: 100%;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h1 class='main-header'>VOKSEWERK - vaekst via udvikling</h1>",
        unsafe_allow_html=True,
    )


def render_sidebar(config: AppConfig) -> tuple[str, str, object | None]:
    api_key = config.api_key
    with st.sidebar:
        st.markdown(
            f"<h2 style='color:{VOKSEWERK_GREEN}'>Kontrolpanel</h2>",
            unsafe_allow_html=True,
        )
        if not api_key:
            api_key = st.text_input("Indtast Groq API-noegle manuelt:", type="password")

        app_mode = st.selectbox("Vaelg modul", CHAT_MODES)
        st.caption(f"Vault: `{config.vault_path}`")
        st.caption(f"Maks filstoerrelse: {config.max_upload_size_mb} MB")
        st.caption(f"Maks promptlaengde: {config.max_prompt_chars} tegn")
        st.caption(f"Logniveau: {config.log_level}")
        st.button("Ryd chat", on_click=clear_chat_history)
        st.divider()

        uploaded_file = None
        if app_mode == "Case Analyse (Audit)":
            st.markdown("**Upload Kundecase**")
            uploaded_file = st.file_uploader(
                "Vaelg fil",
                type=list(SUPPORTED_UPLOAD_TYPES),
                label_visibility="collapsed",
            )

    return api_key.strip(), app_mode, uploaded_file


def render_messages() -> None:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_health_panel(status: AppStatus) -> None:
    with st.expander("Systemstatus", expanded=False):
        st.write(f"API-noegle konfigureret: {'Ja' if status.api_key_configured else 'Nej'}")
        st.write(f"Vault-sti fundet: {'Ja' if status.vault_path_exists else 'Nej'}")
        st.write(f"Vault-filer fundet: {status.vault_document_count}")
        st.write(f"Aktivt modul: {status.active_mode}")
        st.write(f"Chat klar: {'Ja' if status.chat_ready else 'Nej'}")
        if status.active_mode == "Case Analyse (Audit)":
            st.write(f"Upload klar: {'Ja' if status.upload_ready else 'Nej'}")
        if status.startup_error:
            st.write(f"Startup-fejl: {status.startup_error}")
        st.caption(f"Logfil: `{LOG_FILE}`")


def render_status(config: AppConfig, issues: list[str], vault_index, startup_error: str | None) -> None:
    if issues:
        for issue in issues:
            st.warning(issue)
        st.info("Ret ovenstaaende, og genindlaes derefter appen.")
        return

    if startup_error:
        st.error(f"Startup kunne ikke gennemfoeres: {startup_error}")
        st.info("Se logfilen for flere detaljer, og proev derefter igen.")
        return

    if vault_index is None:
        st.warning("Vault blev fundet, men der kunne ikke indlaeses nogen markdown-filer.")
        return

    st.caption(f"Vault-indeks indlaest fra `{config.vault_path}`")


def handle_chat(app_mode: str, uploaded_file, vault_index, config: AppConfig) -> None:
    render_messages()
    placeholder = "Hvad er den naeste strategiske udfordring?"
    chat_ready, disabled_reason = get_chat_readiness(app_mode, vault_index, uploaded_file)
    if disabled_reason:
        st.caption(disabled_reason)

    prompt = st.chat_input(placeholder, disabled=not chat_ready)
    if not prompt:
        return

    try:
        prompt = validate_prompt(prompt, config.max_prompt_chars)
    except ValueError as exc:
        st.warning(str(exc))
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Voksewerk analyserer..."):
            try:
                LOGGER.info("Behandler prompt i modulet '%s'", app_mode)
                if app_mode == CHAT_MODES[1]:
                    res_text = run_case_audit(vault_index, prompt, uploaded_file, config)
                else:
                    res_text = run_strategic_query(vault_index, prompt)
            except Exception as exc:
                LOGGER.exception("Fejl under behandling af prompt")
                res_text = f"Jeg kunne ikke gennemfoere analysen: {exc}"

            st.markdown(res_text)
            st.session_state.messages.append({"role": "assistant", "content": res_text})


def main() -> None:
    config = load_config()
    configure_logging(config.log_level)
    render_branding()
    ensure_session_state(CHAT_MODES)

    api_key, app_mode, uploaded_file = render_sidebar(config)
    maybe_reset_chat_for_mode(app_mode)

    startup = initialize_app(config, api_key)
    if not startup.issues and not startup.startup_error:
        vault_index = load_cached_vault_index(
            config.vault_path,
            api_key,
            config.groq_model,
            config.embed_model,
        )
        startup = type(startup)(
            issues=startup.issues,
            vault_index=vault_index,
            startup_error=startup.startup_error,
            vault_document_count=startup.vault_document_count,
        )
    status = build_status(
        config.vault_path,
        api_key,
        app_mode,
        uploaded_file,
        startup.vault_document_count,
    )

    chat_ready, _ = get_chat_readiness(app_mode, startup.vault_index, uploaded_file)
    status = with_status(status, chat_ready=chat_ready, startup_error=startup.startup_error)

    render_status(config, startup.issues, startup.vault_index, startup.startup_error)
    render_health_panel(status)
    handle_chat(app_mode, uploaded_file, startup.vault_index, config)
