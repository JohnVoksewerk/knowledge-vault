from assistant_app.config import (
    APP_DIR,
    CHAT_MODES,
    DEFAULT_EMBED_MODEL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MODEL,
    DEFAULT_VAULT_PATH,
    LOG_DIR,
    LOG_FILE,
    MAX_PROMPT_CHARS,
    MAX_UPLOAD_SIZE_MB,
    SUPPORTED_UPLOAD_TYPES,
    VOKSEWERK_GREEN,
    VOKSEWERK_NAVY,
    AppConfig,
    configure_logging,
    load_config,
    normalize_log_level,
)
from assistant_app.services import (
    build_audit_prompt,
    build_vault_index,
    configure_models,
    count_vault_documents,
    load_vault_documents,
    read_uploaded_case,
    run_case_audit,
    run_strategic_query,
    validate_environment,
    validate_prompt,
)
from assistant_app.startup import StartupResult, initialize_app
from assistant_app.state import (
    AppStatus,
    build_status,
    clear_chat_history,
    ensure_session_state,
    get_chat_readiness,
    maybe_reset_chat_for_mode,
    with_status,
)
from assistant_app.ui import main
