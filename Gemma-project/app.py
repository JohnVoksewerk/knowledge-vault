import glob
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
from llama_index.readers.file import PDFReader


LOGGER = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / ".streamlit"
LOG_FILE = LOG_DIR / "app.log"

DEFAULT_VAULT_PATH = r"C:\Obsidian\obsidian-knowledge-vault"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SUPPORTED_UPLOAD_TYPES = ("pdf", "txt", "md")
MAX_UPLOAD_SIZE_MB = 10
CHAT_MODES = ("Strategisk Sparring", "Case Analyse (Audit)")
VOKSEWERK_GREEN = "#9ac31c"
VOKSEWERK_NAVY = "#002a3a"


@dataclass(frozen=True)
class AppConfig:
    api_key: str
    vault_path: str
    groq_model: str
    embed_model: str
    max_upload_size_mb: int
    log_level: str


@dataclass(frozen=True)
class AppStatus:
    api_key_configured: bool
    vault_path_exists: bool
    vault_document_count: int
    active_mode: str
    upload_ready: bool


def configure_logging(log_level: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.handlers.clear()
    LOGGER.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)
    LOGGER.propagate = False


def env_or_default(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def env_int_or_default(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        LOGGER.warning("Ugyldig heltalsvaerdi for %s: %s. Bruger default.", name, value)
        return default


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        api_key=os.getenv("GROQ_API_KEY", "").strip(),
        vault_path=env_or_default("VAULT_PATH", DEFAULT_VAULT_PATH),
        groq_model=env_or_default("GROQ_MODEL", DEFAULT_MODEL),
        embed_model=env_or_default("EMBED_MODEL", DEFAULT_EMBED_MODEL),
        max_upload_size_mb=env_int_or_default("MAX_UPLOAD_SIZE_MB", MAX_UPLOAD_SIZE_MB),
        log_level=env_or_default("LOG_LEVEL", "INFO"),
    )


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


def ensure_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_mode" not in st.session_state:
        st.session_state.last_mode = CHAT_MODES[0]


def maybe_reset_chat_for_mode(app_mode: str) -> None:
    if st.session_state.last_mode != app_mode:
        st.session_state.messages = []
        st.session_state.last_mode = app_mode


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
        st.caption(f"Logniveau: {config.log_level}")
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


def validate_environment(config: AppConfig, api_key: str) -> list[str]:
    issues = []
    if not api_key:
        issues.append("GROQ_API_KEY mangler i `.env` eller som manuelt input.")
    if not config.vault_path:
        issues.append("VAULT_PATH er tom.")
    elif not os.path.isdir(config.vault_path):
        issues.append(f"Vault-stien blev ikke fundet: `{config.vault_path}`")
    return issues


def count_vault_documents(vault_path: str) -> int:
    if not vault_path or not os.path.isdir(vault_path):
        return 0
    pattern = os.path.join(vault_path, "**", "*.md")
    return len(glob.glob(pattern, recursive=True))


def build_status(config: AppConfig, api_key: str, app_mode: str, uploaded_file) -> AppStatus:
    vault_document_count = count_vault_documents(config.vault_path)
    return AppStatus(
        api_key_configured=bool(api_key),
        vault_path_exists=bool(config.vault_path) and os.path.isdir(config.vault_path),
        vault_document_count=vault_document_count,
        active_mode=app_mode,
        upload_ready=uploaded_file is not None,
    )


def configure_models(config: AppConfig, api_key: str) -> None:
    Settings.llm = Groq(model=config.groq_model, api_key=api_key)
    Settings.embed_model = HuggingFaceEmbedding(model_name=config.embed_model)


def load_vault_documents(vault_path: str) -> list[Document]:
    documents: list[Document] = []
    pattern = os.path.join(vault_path, "**", "*.md")
    for file_path in glob.glob(pattern, recursive=True):
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                documents.append(
                    Document(
                        text=handle.read(),
                        metadata={"source": file_path},
                    )
                )
        except Exception as exc:
            LOGGER.warning("Kunne ikke laese vault-fil %s: %s", file_path, exc)
    return documents


@st.cache_resource(show_spinner="Indlaeser Obsidian Vault...")
def build_vault_index(vault_path: str, api_key: str, groq_model: str, embed_model: str):
    if not api_key or not vault_path or not os.path.isdir(vault_path):
        return None

    Settings.llm = Groq(model=groq_model, api_key=api_key)
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)

    documents = load_vault_documents(vault_path)
    if not documents:
        return None

    return VectorStoreIndex.from_documents(documents)


def read_uploaded_case(uploaded_file, max_upload_size_mb: int) -> list[Document]:
    if uploaded_file is None:
        raise ValueError("Upload en kundecase for at koere audit.")

    file_size = len(uploaded_file.getbuffer())
    max_size = max_upload_size_mb * 1024 * 1024
    if file_size > max_size:
        raise ValueError(f"Filen er for stor. Maks stoerrelse er {max_upload_size_mb} MB.")

    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    if suffix == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(uploaded_file.getbuffer())
            temp_path = temp_file.name
        try:
            return PDFReader().load_data(file=temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    if suffix in {".txt", ".md"}:
        try:
            case_text = uploaded_file.getvalue().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Tekstfilen skal vaere UTF-8-kodet.") from exc
        if not case_text.strip():
            raise ValueError("Den uploadede fil er tom.")
        return [Document(text=case_text, metadata={"source": uploaded_file.name})]

    raise ValueError("Filtypen understoettes ikke endnu.")


def build_audit_prompt(prompt: str, obsidian_context: str) -> str:
    return f"""
Du er Voksewerks chefstrateg. Din opgave er at udfoere en KRITISK STRATEGISK AUDIT af den vedhaeftede case.

HER ER DIN KERNEVIDEN FRA OBSIDIAN (Brug dette som din linse):
{obsidian_context}

HER ER CASEN DU SKAL ANALYSERE:
{prompt}

INSTRUKSER:
- Lav ALDRIG et resume.
- Identificer 3-5 kritiske blinde vinkler i casen baseret paa Obsidian-viden.
- Paapeg specifikt hvor casen bryder med Voksewerk-metodikken.
- Stil 3 udfordrende spoergsmaal, som jeg skal tage med til kunden.
""".strip()


def validate_prompt(prompt: str) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompten er tom.")
    if len(cleaned) < 3:
        raise ValueError("Prompten er for kort til at give et brugbart svar.")
    return cleaned


def run_strategic_query(vault_index: VectorStoreIndex, prompt: str) -> str:
    response = vault_index.as_query_engine().query(prompt)
    return response.response


def run_case_audit(vault_index: VectorStoreIndex, prompt: str, uploaded_file, config: AppConfig) -> str:
    vault_query_engine = vault_index.as_query_engine(similarity_top_k=5)
    obsidian_context = vault_query_engine.query(
        "Find mine vigtigste strategiske principper, metoder og advarsler, "
        f"der er relevante for dette emne: {prompt}"
    )
    case_docs = read_uploaded_case(uploaded_file, config.max_upload_size_mb)
    case_index = VectorStoreIndex.from_documents(case_docs)
    audit_prompt = build_audit_prompt(prompt, str(obsidian_context))
    response = case_index.as_query_engine().query(audit_prompt)
    return response.response


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
        if status.active_mode == "Case Analyse (Audit)":
            st.write(f"Upload klar: {'Ja' if status.upload_ready else 'Nej'}")
        st.caption(f"Logfil: `{LOG_FILE}`")


def render_status(config: AppConfig, issues: list[str], vault_index) -> None:
    if issues:
        for issue in issues:
            st.warning(issue)
        st.info("Ret ovenstaaende, og genindlaes derefter appen.")
        return

    if vault_index is None:
        st.warning("Vault blev fundet, men der kunne ikke indlaeses nogen markdown-filer.")
        return

    st.caption(f"Vault-indeks indlaest fra `{config.vault_path}`")


def handle_chat(app_mode: str, uploaded_file, vault_index, config: AppConfig) -> None:
    render_messages()
    placeholder = "Hvad er den naeste strategiske udfordring?"
    prompt = st.chat_input(placeholder, disabled=vault_index is None)
    if not prompt:
        return

    try:
        prompt = validate_prompt(prompt)
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
                if app_mode == "Case Analyse (Audit)":
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
    ensure_session_state()

    api_key, app_mode, uploaded_file = render_sidebar(config)
    maybe_reset_chat_for_mode(app_mode)
    status = build_status(config, api_key, app_mode, uploaded_file)

    issues = validate_environment(config, api_key)
    vault_index = None
    if not issues:
        configure_models(config, api_key)
        vault_index = build_vault_index(
            config.vault_path,
            api_key,
            config.groq_model,
            config.embed_model,
        )

    render_status(config, issues, vault_index)
    render_health_panel(status)
    handle_chat(app_mode, uploaded_file, vault_index, config)


if __name__ == "__main__":
    main()
