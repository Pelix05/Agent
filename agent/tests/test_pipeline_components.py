import tempfile
from pathlib import Path
import os
import importlib.util
import importlib.machinery


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
# Ensure the agent package directory is first on sys.path so modules that use
# `from prompts import ...` or similar can be imported when loading files by path.
import sys
agent_pkg_path = str(ROOT / 'agent')
if agent_pkg_path not in sys.path:
    sys.path.insert(0, agent_pkg_path)

analyzer_cpp = load_module_from_path('analyzer_cpp', ROOT / 'agent' / 'analyzer_cpp.py')
analyzer_py = load_module_from_path('analyzer_py', ROOT / 'agent' / 'analyzer_py.py')
pipeline = load_module_from_path('pipeline', ROOT / 'agent' / 'pipeline.py')
patch_parser = load_module_from_path('patch_parser', ROOT / 'agent' / 'patch_parser.py')


def test_analyzer_cpp_writes_report(tmp_path, monkeypatch):
    # Prepare fake cpp_project with a simple file
    root = Path(pipeline.BASE_DIR)
    cpp_dir = root / "cpp_project"
    cpp_dir.mkdir(exist_ok=True)
    sample = cpp_dir / "sample.cpp"
    sample.write_text("int main() { return 0; }")

    fake_report = "sample.cpp:1: warning: fake warning"

    def fake_run(cmd, cwd=None):
        return fake_report

    report = analyzer_cpp.analyze_cpp(run_cmd=fake_run)
    assert "fake warning" in report


def test_analyzer_py_writes_report(tmp_path, monkeypatch):
    root = Path(pipeline.BASE_DIR)
    py_dir = root / "python_repo"
    py_dir.mkdir(exist_ok=True)
    sample = py_dir / "sample.py"
    sample.write_text("print('hi')")

    fake_report = "sample.py:1:0: note: fake"

    def fake_run(cmd, cwd=None):
        return fake_report

    report = analyzer_py.analyze_python(run_cmd=fake_run)
    assert "fake" in report


def test_patch_parser_accepts_valid_diff(tmp_path):
    report_text = "cpp_project/sample.cpp:1: warning"
    allowed = patch_parser.parse_changed_files_from_report(report_text)

    diff = """
diff --git a/cpp_project/sample.cpp b/cpp_project/sample.cpp
--- a/cpp_project/sample.cpp
+++ b/cpp_project/sample.cpp
@@ -1 +1 @@
-int main() { return 1; }
+int main() { return 0; }
"""

    assert patch_parser.validate_unified_diff(diff, allowed) is True


def test_pipeline_writes_patches(tmp_path, monkeypatch):
    # Prepare minimal report and snippet files
    root = Path(pipeline.BASE_DIR)
    report_file = root / "analysis_report_cpp.txt"
    snippets_dir = root / "snippets"
    snippets_dir.mkdir(exist_ok=True)
    snippet_file = snippets_dir / "bug_snippets_cpp.txt"

    report_file.write_text("cpp_project/sample.cpp:1: warning")
    snippet_file.write_text("--- cpp_project/sample.cpp:1 ---\nint main() { return 1; }")

    # Fake LLM returns a valid diff
    def fake_ask(prompt):
        return (
            "diff --git a/cpp_project/sample.cpp b/cpp_project/sample.cpp\n"
            "--- a/cpp_project/sample.cpp\n"
            "+++ b/cpp_project/sample.cpp\n"
            "@@ -1 +1 @@\n"
            "-int main() { return 1; }\n"
            "+int main() { return 0; }\n"
        )

    monkeypatch.setattr(pipeline, 'ask_llm', fake_ask)
    # Ensure parser functions are available
    monkeypatch.setattr(pipeline, 'parse_changed_files_from_report', patch_parser.parse_changed_files_from_report)
    monkeypatch.setattr(pipeline, 'validate_unified_diff', patch_parser.validate_unified_diff)

    pipeline.run_pipeline()

    out = (root / 'patches' / 'all_patches.md').read_text()
    assert 'diff --git' in out
