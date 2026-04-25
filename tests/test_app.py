import os
import unittest
from unittest.mock import mock_open, patch

from llama_index.core import Document

import app


class UploadedFileStub:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return memoryview(self._data)

    def getvalue(self):
        return self._data


class LoadConfigTests(unittest.TestCase):
    def test_load_config_uses_defaults_when_optional_values_missing(self):
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "secret",
                "VAULT_PATH": "",
                "GROQ_MODEL": "",
                "EMBED_MODEL": "",
                "MAX_UPLOAD_SIZE_MB": "10",
                "MAX_PROMPT_CHARS": "4000",
                "LOG_LEVEL": "invalid",
            },
            clear=False,
        ):
            config = app.load_config()

        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.vault_path, app.DEFAULT_VAULT_PATH)
        self.assertEqual(config.groq_model, app.DEFAULT_MODEL)
        self.assertEqual(config.embed_model, app.DEFAULT_EMBED_MODEL)
        self.assertEqual(config.max_upload_size_mb, 10)
        self.assertEqual(config.max_prompt_chars, 4000)
        self.assertEqual(config.log_level, "INFO")

    def test_validate_environment_reports_missing_key_and_missing_vault(self):
        config = app.AppConfig(
            api_key="",
            vault_path=r"C:\does-not-exist",
            groq_model=app.DEFAULT_MODEL,
            embed_model=app.DEFAULT_EMBED_MODEL,
            max_upload_size_mb=10,
            log_level="INFO",
            max_prompt_chars=4000,
        )

        issues = app.validate_environment(config, "")

        self.assertEqual(len(issues), 2)
        self.assertIn("GROQ_API_KEY", issues[0])
        self.assertIn("Vault-stien", issues[1])


class UploadedCaseTests(unittest.TestCase):
    def test_read_uploaded_case_accepts_utf8_text(self):
        uploaded = UploadedFileStub("case.txt", "Strategisk note".encode("utf-8"))

        docs = app.read_uploaded_case(uploaded, max_upload_size_mb=1)

        self.assertEqual(len(docs), 1)
        self.assertIsInstance(docs[0], Document)
        self.assertEqual(docs[0].text, "Strategisk note")

    def test_read_uploaded_case_rejects_empty_text_file(self):
        uploaded = UploadedFileStub("case.md", b"   ")

        with self.assertRaisesRegex(ValueError, "tom"):
            app.read_uploaded_case(uploaded, max_upload_size_mb=1)

    def test_read_uploaded_case_rejects_large_files(self):
        uploaded = UploadedFileStub("case.txt", b"a" * (2 * 1024 * 1024))

        with self.assertRaisesRegex(ValueError, "for stor"):
            app.read_uploaded_case(uploaded, max_upload_size_mb=1)

    def test_load_vault_documents_reads_markdown_files(self):
        vault_path = r"C:\vault"
        file_path = os.path.join(vault_path, "note.md")
        with patch("app.glob.glob", return_value=[file_path]), patch(
            "builtins.open",
            mock_open(read_data="Indhold fra vault"),
        ):
            docs = app.load_vault_documents(vault_path)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].text, "Indhold fra vault")
        self.assertEqual(docs[0].metadata["source"], file_path)


class RuntimeGuardTests(unittest.TestCase):
    def test_validate_prompt_rejects_blank_prompt(self):
        with self.assertRaisesRegex(ValueError, "tom"):
            app.validate_prompt("   ", 4000)

    def test_validate_prompt_rejects_short_prompt(self):
        with self.assertRaisesRegex(ValueError, "for kort"):
            app.validate_prompt("ok", 4000)

    def test_validate_prompt_rejects_long_prompt(self):
        with self.assertRaisesRegex(ValueError, "for lang"):
            app.validate_prompt("a" * 4010, 4000)

    def test_build_status_reflects_current_state(self):
        config = app.AppConfig(
            api_key="secret",
            vault_path=r"C:\does-not-exist",
            groq_model=app.DEFAULT_MODEL,
            embed_model=app.DEFAULT_EMBED_MODEL,
            max_upload_size_mb=10,
            log_level="INFO",
            max_prompt_chars=4000,
        )

        status = app.build_status(config, "secret", "Case Analyse (Audit)", uploaded_file=None)

        self.assertTrue(status.api_key_configured)
        self.assertFalse(status.vault_path_exists)
        self.assertEqual(status.vault_document_count, 0)
        self.assertEqual(status.active_mode, "Case Analyse (Audit)")
        self.assertFalse(status.upload_ready)


if __name__ == "__main__":
    unittest.main()
