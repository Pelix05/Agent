BUG_FIX_PROMPT = """
Role: You are an expert programmer.

Problem: {bug_report}

Code:
{code_snippet}

Task: Provide a patch in unified diff format (diff -u) that fixes this bug.
Before the patch, include a short explanation (2-3 sentences) describing the root cause and why the change fixes it.

Requirements:
- Output must be a valid unified diff that can be applied with `git apply`.
- The diff must include leading header lines starting with `diff --git a/<path> b/<path>`.
- Use `+++` and `---` file markers and context lines.
- Only modify files that are mentioned in the `analysis_report` or `bug_snippets` input.
- Keep changes minimal and preserve original code style.

If you cannot produce a valid unified diff, reply with the single line: ERROR: CANNOT_GENERATE_PATCH
"""