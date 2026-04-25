import os
import tempfile

from llama_index.core import Document, VectorStoreIndex
from llama_index.readers.file import PDFReader

from assistant_app.config import AppConfig


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

