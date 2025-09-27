import os
from pathlib import Path
import pytest

import agent.pipeline as pipeline_module


def test_pipeline_writes_patches(tmp_path, monkeypatch):
    # Setup a temporary agent structure
    base = tmp_path / 'agent'
    base.mkdir()
    (base / 'snippets').mkdir()
    (base / 'patches').mkdir()

    # write an analysis report and a snippet file
    report = base / 'analysis_report_cpp.txt'
    report.write_text('dummy')
    snippet = base / 'snippets' / 'bug_snippets_cpp.txt'
    snippet.write_text('--- foo.cpp:1 ---\nint x=0;')

    # monkeypatch paths inside pipeline module
    monkeypatch.setattr(pipeline_module, 'BASE_DIR', base)
    monkeypatch.setattr(pipeline_module, 'SNIPPETS_DIR', base / 'snippets')
    monkeypatch.setattr(pipeline_module, 'PATCHES_DIR', base / 'patches')
    monkeypatch.setattr(pipeline_module, 'REPORT_FILE', report)
    monkeypatch.setattr(pipeline_module, 'SNIPPET_FILE', snippet)
    monkeypatch.setattr(pipeline_module, 'PATCH_FILE', base / 'patches' / 'all_patches.diff')

    # stub ask_llm to return a valid diff
    VALID_DIFF = 'diff --git a/foo.cpp b/foo.cpp\n--- a/foo.cpp\n+++ b/foo.cpp\n@@ -1 +1 @@\n-int a;\n+int a=1;\n'
    monkeypatch.setattr(pipeline_module, 'ask_llm', lambda prompt: VALID_DIFF)

    # run pipeline
    pipeline_module.run_pipeline()

    out_file = base / 'patches' / 'all_patches.diff'
    assert out_file.exists()
    content = out_file.read_text()
    assert 'diff --git a/foo.cpp b/foo.cpp' in content
