import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from agent_system.constants import AGENT_CHATBOT, AGENT_CODE_EDITOR, AGENT_ORCHESTRATOR, AGENT_PROJECT_READER
from agent_system.graph import route_next_agent
from agent_system.project_reader_agent import _bounded_context, projectReader
from agent_system.code_editor_agent import (
    _decode_plan,
    _natural_create_button_operation,
    _natural_delete_button_operation,
    _prepare_operation,
    _resolve_target,
    _safe_target,
)
from agent_system.repository_tools import inspect_dom, inspect_file_relationships, inspect_symbol, read_project_file


class OrchestratorSelectionTests(unittest.TestCase):
    def test_read_tool_returns_exact_numbered_lines(self):
        path = Path.cwd() / "tmp_repository_tool_sample.html"
        try:
            path.write_text("uno\ndos\ntres\n", encoding="utf-8")
            with patch("agent_system.repository_tools._project_root", return_value=Path.cwd()):
                result = read_project_file.invoke({"path": path.name, "start_line": 2, "end_line": 3})
            self.assertIn("2: dos", result["content"])
            self.assertIn("3: tres", result["content"])
        finally:
            if path.exists(): path.unlink()

    def test_dom_tool_finds_precise_parent_and_line(self):
        path = Path.cwd() / "tmp_repository_tool_screen.aspx"
        try:
            path.write_text('<form id="main">\n<div class="actions"><button id="save">Guardar</button></div>\n</form>', encoding="utf-8")
            with patch("agent_system.repository_tools._project_root", return_value=Path.cwd()):
                result = inspect_dom.invoke({"path": path.name, "selector_or_text": "save"})
            self.assertEqual(result["matching_elements"], 1)
            self.assertEqual(result["elements"][0]["parent"], "div.actions")
            self.assertEqual(result["elements"][0]["line"], 2)
        finally:
            if path.exists(): path.unlink()

    def test_relationship_tool_finds_codebehind_and_assets(self):
        page = Path.cwd() / "tmp_repository_tool_Page.aspx"
        codebehind = Path(f"{page}.cs")
        script = page.with_suffix(".js")
        try:
            page.write_text('<%@ Page CodeFile="Page.aspx.cs" %><script src="Page.js"></script>', encoding="utf-8")
            codebehind.write_text("class Page {}", encoding="utf-8")
            script.write_text("function save() {}", encoding="utf-8")
            with patch("agent_system.repository_tools._project_root", return_value=Path.cwd()):
                result = inspect_file_relationships.invoke({"path": page.name})
            self.assertTrue(any(item.endswith(codebehind.name) for item in result["related_files"]))
            self.assertTrue(any(item.endswith(script.name) for item in result["related_files"]))
        finally:
            for path in (page, codebehind, script):
                if path.exists(): path.unlink()
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

    def test_orchestrator_does_not_edit_when_asked_how_to_create_a_user(self):
        state = {"messages": [HumanMessage(content="Explicame paso a paso como crear un usuario")]}
        self.assertEqual(route_next_agent(state), AGENT_PROJECT_READER)

    def test_orchestrator_does_not_edit_when_asked_for_creation_process(self):
        state = {"messages": [HumanMessage(content="¿Cuál es el proceso para crear un usuario?")]}
        self.assertEqual(route_next_agent(state), AGENT_PROJECT_READER)

    def test_editor_rejects_paths_outside_repository(self):
        from pathlib import Path
        with self.assertRaises(ValueError):
            _safe_target(Path.cwd() / "repositorios", "../secreto.txt")

    def test_editor_accepts_json_plan(self):
        plan = _decode_plan('{"summary":"ok","operations":[]}')
        self.assertEqual(plan["summary"], "ok")

    def test_editor_inserts_button_after_exact_anchor(self):
        from pathlib import Path

        root = Path.cwd()
        path = root / "tmp_insert_button_test.txt"
        path.write_text(
            '<div>\n<button id="lnk_registrarse" type="button" class="btn btn-primary" style="margin-top: 8px; width: 100%; max-width: 220px;">Registrarme</button>\n</div>\n',
            encoding="utf-8",
        )
        try:
            target, content, existed = _prepare_operation(
                root,
                {
                    "action": "replace",
                    "path": "tmp_insert_button_test.txt",
                    "old_text": '<button id="lnk_registrarse" type="button" class="btn btn-primary" style="margin-top: 8px; width: 100%; max-width: 220px;">Registrarme</button>',
                    "new_text": '<button id="lnk_registrarse" type="button" class="btn btn-primary" style="margin-top: 8px; width: 100%; max-width: 220px;">Registrarme</button>\n<button id="TEST" type="button" class="btn btn-primary" style="margin-top: 8px; width: 100%; max-width: 220px;">TEST</button>',
                },
            )
            self.assertTrue(existed)
            self.assertIn('id="TEST"', content)
            self.assertEqual(target.name, path.name)
        finally:
            if path.exists():
                path.unlink()

    def test_editor_accepts_json_embedded_in_text(self):
        text = (
            'Voy a hacerlo.\n'
            '{"summary":"ok","operations":[{"action":"replace","path":"tmp.txt","old_text":"a","new_text":"b"}]}\n'
            'Hecho.'
        )
        plan = _decode_plan(text)
        self.assertEqual(plan["summary"], "ok")
        self.assertEqual(plan["operations"][0]["path"], "tmp.txt")

    def test_resolve_target_prefers_real_login_file_by_basename(self):
        from pathlib import Path

        root = Path.cwd() / "tmp_login_resolution"
        (root / "a").mkdir(parents=True, exist_ok=True)
        (root / "b" / "WebRH").mkdir(parents=True, exist_ok=True)
        (root / "b" / "WebRH" / "FormularioConcursar").mkdir(parents=True, exist_ok=True)
        first = root / "a" / "Login.aspx"
        second = root / "b" / "WebRH" / "Login.aspx"
        third = root / "b" / "WebRH" / "FormularioConcursar" / "Login.aspx"
        first.write_text("<html></html>", encoding="utf-8")
        second.write_text("<html></html>", encoding="utf-8")
        third.write_text("<html></html>", encoding="utf-8")
        try:
            self.assertEqual(_resolve_target(root, "Login.aspx").as_posix(), second.as_posix())
            self.assertEqual(_resolve_target(root, "WebRH/Login.aspx").as_posix(), second.as_posix())
            self.assertEqual(_resolve_target(root, "FormularioConcursar/Login.aspx").as_posix(), third.as_posix())
        finally:
            if first.exists():
                first.unlink()
            if second.exists():
                second.unlink()
            if third.exists():
                third.unlink()
            if (root / "b" / "WebRH" / "FormularioConcursar").exists():
                (root / "b" / "WebRH" / "FormularioConcursar").rmdir()
            if (root / "b" / "WebRH").exists():
                (root / "b" / "WebRH").rmdir()
            if (root / "b").exists():
                (root / "b").rmdir()
            if (root / "a").exists():
                (root / "a").rmdir()
            if root.exists():
                root.rmdir()

    def test_editor_accepts_whitespace_variants_in_replace(self):
        from pathlib import Path

        root = Path.cwd()
        path = root / "tmp_whitespace_test.txt"
        path.write_text(
            '<div>\n  <a\n    id="lnk_recuperar"\n    style="cursor: pointer;"\n>¿Olvidé mi clave?</a>\n</div>\n',
            encoding="utf-8",
        )
        try:
            target, content, existed = _prepare_operation(
                root,
                {
                    "action": "replace",
                    "path": "tmp_whitespace_test.txt",
                    "old_text": "<a id=\"lnk_recuperar\" style=\"cursor: pointer;\">¿Olvidé mi clave?</a>",
                    "new_text": "<a id=\"lnk_recuperar\" style=\"cursor: pointer;\">¿Olvidé mi clave?</a>\n<a href=\"javascript:void(0);\">Click aqui</a>",
                },
            )
            self.assertTrue(existed)
            self.assertIn("Click aqui", content)
            self.assertEqual(target.name, path.name)
        finally:
            if path.exists():
                path.unlink()

    def test_editor_accepts_absolute_paths_within_repo(self):
        from pathlib import Path

        root = Path.cwd()
        path = root / "tmp_absolute_path_test.txt"
        path.write_text("hola", encoding="utf-8")
        try:
            target, content, existed = _prepare_operation(
                root,
                {
                    "action": "replace",
                    "path": str(path),
                    "old_text": "hola",
                    "new_text": "chau",
                },
            )
            self.assertTrue(existed)
            self.assertEqual(target.resolve(), path.resolve())
            self.assertEqual(content, "chau")
        finally:
            if path.exists():
                path.unlink()

    def test_editor_rejects_absolute_paths_outside_repo(self):
        from pathlib import Path

        root = Path.cwd()
        outside = (root.parent / "outside_repo_test.txt").resolve()
        try:
            with self.assertRaises(ValueError):
                _prepare_operation(
                    root,
                    {
                        "action": "replace",
                        "path": str(outside),
                        "old_text": "hola",
                        "new_text": "chau",
                    },
                )
        finally:
            if outside.exists():
                outside.unlink()

    def test_editor_removes_link_text_even_with_whitespace_variants(self):
        from pathlib import Path

        root = Path.cwd()
        path = root / "tmp_delete_link_test.txt"
        path.write_text(
            '<div>\n  <a href="javascript:void(0);" style="display: inline-block; margin-top: 8px;">Click aqui</a>\n</div>\n',
            encoding="utf-8",
        )
        try:
            target, content, existed = _prepare_operation(
                root,
                {
                    "action": "delete",
                    "path": "tmp_delete_link_test.txt",
                    "old_text": "<a href=\"javascript:void(0);\" style=\"display: inline-block; margin-top: 8px;\">Click aqui</a>",
                    "new_text": "",
                },
            )
            self.assertTrue(existed)
            self.assertNotIn("Click aqui", content)
            self.assertEqual(target.name, path.name)
        finally:
            if path.exists():
                path.unlink()

    def test_natural_prompt_creates_TEST_button_in_login_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "repositorios" / "rrhh" / "WebAsistencia" / "WebRH" / "Login.aspx"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '<div style="position: relative; display: inline-block; width: 260px;">\n'
                '  <button id="fat-btn" data-loading-text="Iniciando..." class="btn btn-primary" style="margin-bottom: 15px;">\n'
                '    Iniciar Sesión\n'
                '  </button>\n'
                '  <br />\n'
                '</div>\n',
                encoding="utf-8",
            )

            op = _natural_create_button_operation('Crea el botón TEST dentro de Login.aspx', root)
            self.assertEqual(op["action"], "replace")
            self.assertEqual(op["path"], "repositorios/rrhh/WebAsistencia/WebRH/Login.aspx")
            self.assertIn('id="btn-test"', op["new_text"])
            self.assertIn('TEST', op["new_text"])

    def test_natural_prompt_creates_TEST_button_with_current_login_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "repositorios" / "rrhh" / "WebAsistencia" / "WebRH" / "Login.aspx"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '<div id="loginControles">\n'
                '  <input type="text" id="usuario" />\n'
                '  <input type="password" id="password" />\n'
                '  <div style="position: relative; display: inline-block; width: 260px;">\n'
                '    <button id="fat-btn" data-loading-text="Iniciando..." class=" btn btn-primary" style="margin-bottom: 15px;">\n'
                '      Iniciar Sesión\n'
                '    </button>\n'
                '    <br />\n'
                '    <a id="lnk_registrarse">Registrarme</a>\n'
                '  </div>\n'
                '</div>\n',
                encoding="utf-8",
            )

            op = _natural_create_button_operation('crea el boton test dentro de login.aspx', root)
            self.assertEqual(op["action"], "replace")
            self.assertIn('btn-test', op["new_text"])
            target, content, existed = _prepare_operation(root, op)
            self.assertTrue(existed)
            self.assertEqual(target.as_posix(), path.as_posix())
            self.assertIn('btn-test', content)
            self.assertIn('TEST', content)

    def test_natural_prompt_creates_generic_custom_button(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "repositorios" / "rrhh" / "WebAsistencia" / "WebRH" / "Login.aspx"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '<div style="position: relative; display: inline-block; width: 260px;">\n'
                '  <button id="fat-btn" data-loading-text="Iniciando..." class="btn btn-primary">\n'
                '    Iniciar Sesión\n'
                '  </button>\n'
                '</div>\n',
                encoding="utf-8",
            )

            op = _natural_create_button_operation('crea el boton ayuda dentro de login.aspx', root)
            self.assertEqual(op["action"], "replace")
            self.assertIn('btn-ayuda', op["new_text"])
            self.assertIn('Ayuda', op["new_text"])
            target, content, existed = _prepare_operation(root, op)
            self.assertTrue(existed)
            self.assertEqual(target.as_posix(), path.as_posix())
            self.assertIn('btn-ayuda', content)
            self.assertIn('Ayuda', content)

    def test_prepare_operation_resolves_real_login_when_plan_uses_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "repositorios" / "rrhh" / "WebAsistencia" / "WebRH" / "Login.aspx"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '<div style="position: relative; display: inline-block; width: 260px;">\n'
                '  <button id="fat-btn" data-loading-text="Iniciando..." class="btn btn-primary">\n'
                '    Iniciar Sesión\n'
                '  </button>\n'
                '</div>\n',
                encoding="utf-8",
            )

            target, content, existed = _prepare_operation(
                root,
                {
                    "action": "replace",
                    "path": "ProyectoNet/General/WEBRH/Login.aspx",
                    "old_text": '<button id="fat-btn" data-loading-text="Iniciando..." class="btn btn-primary">',
                    "new_text": '<button id="fat-btn" data-loading-text="Iniciando..." class="btn btn-primary">\n<button id="btn-test" type="button" class="btn btn-primary">TEST</button>',
                },
            )
            self.assertTrue(existed)
            self.assertEqual(target.as_posix(), path.as_posix())
            self.assertIn('btn-test', content)

    def test_natural_prompt_removes_TEST_button_from_login_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "repositorios" / "rrhh" / "WebAsistencia" / "WebRH" / "Login.aspx"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                '<button id="lnk_registrarse" type="button" class="btn btn-primary">Registrarme</button>\n'
                '<button id="TEST" type="button" class="btn btn-primary">TEST</button>\n',
                encoding="utf-8",
            )

            op = _natural_delete_button_operation('Elimina el botón TEST dentro de Login.aspx', root)
            self.assertEqual(op["action"], "delete")
            self.assertEqual(op["path"], "repositorios/rrhh/WebAsistencia/WebRH/Login.aspx")
            self.assertIn('id="TEST"', op["old_text"])

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
