import glob
import logging
import os
import tempfile

from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq
from llama_index.readers.file import PDFReader

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


def validate_prompt(prompt: str, max_prompt_chars: int) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        raise ValueError("Prompten er tom.")
    if len(cleaned) < 3:
        raise ValueError("Prompten er for kort til at give et brugbart svar.")
    if len(cleaned) > max_prompt_chars:
        raise ValueError(f"Prompten er for lang. Maks laengde er {max_prompt_chars} tegn.")
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

