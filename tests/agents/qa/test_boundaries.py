"""Проверка цитат работает без загрузки графа, API и клиентов провайдеров."""

import subprocess
import sys
import unittest


class EvidenceImportTests(unittest.TestCase):
    def test_evidence_validation_does_not_load_service_dependencies(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; "
                "from sdm.agents.project_qa.evidence import models, validation; "
                "print(','.join(sorted(set(sys.modules) & "
                "{'openai', 'langgraph', 'sqlalchemy', 'fastapi'})))",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "")
