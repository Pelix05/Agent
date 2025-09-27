
BUG_FIX_PROMPT = """
Role: You are an expert programmer.
Problem: {analysis}
Code: {code_snippet}
Task: Provide a patch in unified diff format (diff -u) that fixes this bug.

Output rules:
- First, provide a 2-3 sentence explanation of the fix (plain text), then a blank line, then the unified diff.
- The diff must start with: diff --git a/<path> b/<path>
- The diff must include '--- ' and '+++ ' file headers and context lines, and be applyable with git apply.
- Do not include any additional commentary after the diff.
- If you cannot produce a valid diff, output exactly an empty string.

Objective: Make the output consistent and directly applicable with git apply.
"""
