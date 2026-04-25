import logging
from dataclasses import dataclass

from assistant_app.config import AppConfig
from assistant_app.services import configure_models
from assistant_app.vault import build_vault_index, count_vault_documents, validate_environment


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartupResult:
    issues: list[str]
    vault_index: object | None
    startup_error: str | None
    vault_document_count: int


def initialize_app(config: AppConfig, api_key: str) -> StartupResult:
    issues = validate_environment(config, api_key)
    vault_document_count = count_vault_documents(config.vault_path)
    if issues:
        return StartupResult(
            issues=issues,
            vault_index=None,
            startup_error=None,
            vault_document_count=vault_document_count,
        )

    try:
        configure_models(config, api_key)
        vault_index = build_vault_index(
            config.vault_path,
            api_key,
            config.groq_model,
            config.embed_model,
        )
        return StartupResult(
            issues=[],
            vault_index=vault_index,
            startup_error=None,
            vault_document_count=vault_document_count,
        )
    except Exception as exc:
        LOGGER.exception("Fejl under startup og indeksinitialisering")
        return StartupResult(
            issues=[],
            vault_index=None,
            startup_error=str(exc),
            vault_document_count=vault_document_count,
        )

