BUG_FIX_PROMPT = """
You are an expert software engineer.

Your task: generate a **valid unified diff patch** to fix bugs in the given code snippet,
based on the static analysis report.

# Analysis Report:
{analysis}

# Buggy Code Snippet:
{code_snippet}

# Instructions (STRICT):
- Output ONLY a unified diff patch that can be applied with `git apply`.
- Patch MUST begin with:
  diff --git a/<file> b/<file>
- MUST include these headers for each file:
  • index <hash>..<hash> <mode>
  • --- a/<file>
  • +++ b/<file>
- The diff body MUST contain actual changes (no empty diffs).
- Do NOT include markdown formatting (no ```diff or ```).
- Do NOT include explanations, natural text, or comments outside of diff.
- Do NOT invent file paths. Always reuse the ones shown in the snippet/report.
- If no valid changes are needed, output exactly: ""
- The patch must be syntactically correct and compilable (C++ or Python).

# Output:
Return ONLY the raw unified diff patch (or "" if no changes).
"""

