import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


LOGGER = logging.getLogger(__name__)
APP_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = APP_DIR / ".streamlit"
LOG_FILE = LOG_DIR / "app.log"

DEFAULT_VAULT_PATH = r"C:\Obsidian\obsidian-knowledge-vault"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LOG_LEVEL = "INFO"
SUPPORTED_UPLOAD_TYPES = ("pdf", "txt", "md")
MAX_UPLOAD_SIZE_MB = 10
MAX_PROMPT_CHARS = 4000
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
    max_prompt_chars: int


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


def normalize_log_level(value: str) -> str:
    normalized = value.strip().upper()
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    return normalized if normalized in allowed else DEFAULT_LOG_LEVEL


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        api_key=os.getenv("GROQ_API_KEY", "").strip(),
        vault_path=env_or_default("VAULT_PATH", DEFAULT_VAULT_PATH),
        groq_model=env_or_default("GROQ_MODEL", DEFAULT_MODEL),
        embed_model=env_or_default("EMBED_MODEL", DEFAULT_EMBED_MODEL),
        max_upload_size_mb=max(1, env_int_or_default("MAX_UPLOAD_SIZE_MB", MAX_UPLOAD_SIZE_MB)),
        log_level=normalize_log_level(env_or_default("LOG_LEVEL", DEFAULT_LOG_LEVEL)),
        max_prompt_chars=max(250, env_int_or_default("MAX_PROMPT_CHARS", MAX_PROMPT_CHARS)),
    )

