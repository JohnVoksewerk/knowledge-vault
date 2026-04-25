import glob
import logging
import os

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq

from assistant_app.config import AppConfig


LOGGER = logging.getLogger(__name__)


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


def build_vault_index(vault_path: str, api_key: str, groq_model: str, embed_model: str):
    if not api_key or not vault_path or not os.path.isdir(vault_path):
        return None

    Settings.llm = Groq(model=groq_model, api_key=api_key)
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model)

    documents = load_vault_documents(vault_path)
    if not documents:
        return None

    return VectorStoreIndex.from_documents(documents)


def run_strategic_query(vault_index: VectorStoreIndex, prompt: str) -> str:
    response = vault_index.as_query_engine().query(prompt)
    return response.response

