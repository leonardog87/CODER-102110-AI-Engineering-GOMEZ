import unittest

from langchain_core.messages import HumanMessage

from agent_system.constants import AGENT_CHATBOT, AGENT_CODE_EDITOR, AGENT_ORCHESTRATOR, AGENT_PROJECT_READER
from agent_system.graph import route_next_agent
from agent_system.project_reader_agent import _bounded_context, projectReader
from agent_system.code_editor_agent import _decode_plan, _safe_target


class OrchestratorSelectionTests(unittest.TestCase):
    def test_orchestrator_selects_chatbot_for_general_questions(self):
        state = {"messages": [HumanMessage(content="¿Qué servicios ofrece la empresa?")]}
        self.assertEqual(route_next_agent(state), AGENT_CHATBOT)

    def test_orchestrator_selects_project_reader_for_analysis_requests(self):
        state = {"messages": [HumanMessage(content="Lee el proyecto y explica su arquitectura y procesos")]}
        self.assertEqual(route_next_agent(state), AGENT_PROJECT_READER)

    def test_orchestrator_selects_project_reader_for_specific_file_requests(self):
        state = {"messages": [HumanMessage(content="¿Qué es principal.aspx?")]}
        self.assertEqual(route_next_agent(state), AGENT_PROJECT_READER)

    def test_orchestrator_selects_code_editor_for_modification_requests(self):
        state = {"messages": [HumanMessage(content="Modifica api.py y crea un nuevo endpoint para consultar salud")]}
        self.assertEqual(route_next_agent(state), AGENT_CODE_EDITOR)

    def test_orchestrator_does_not_edit_when_asked_about_a_file(self):
        state = {"messages": [HumanMessage(content="Explica el archivo api.py y su función")]}
        self.assertEqual(route_next_agent(state), AGENT_PROJECT_READER)

    def test_editor_rejects_paths_outside_repository(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            _safe_target(Path.cwd() / "repositorios", "../secreto.txt")

    def test_editor_accepts_json_plan(self):
        plan = _decode_plan('{"summary":"ok","operations":[]}')
        self.assertEqual(plan["summary"], "ok")

    def test_reader_context_keeps_primary_and_related_evidence(self):
        context = _bounded_context("entrada " * 3000, "implementacion " * 3000)
        self.assertLessEqual(len(context), 20100)
        self.assertIn("entrada", context)
        self.assertIn("implementacion", context)

    def test_project_reader_reads_specific_file_requested_by_user(self):
        state = {"messages": [HumanMessage(content="¿Qué es principal.aspx?")]}
        result = projectReader(state)
        context = str(result.get("project_context", ""))
        self.assertIn("Principal.aspx", context)
        self.assertIn("BarraMenu", context)
        self.assertIn("CIOT", context)

    def test_orchestrator_exists_and_is_named(self):
        self.assertEqual(AGENT_ORCHESTRATOR, "orchestrator")
        self.assertEqual(AGENT_PROJECT_READER, "projectReader")
        self.assertEqual(AGENT_CODE_EDITOR, "codeEditor")


if __name__ == "__main__":
    unittest.main()
