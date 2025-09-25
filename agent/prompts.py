
BUG_FIX_PROMPT = """
You are an expert software engineer.

Your task: Generate a valid unified diff patch (`diff -u`) to fix the bug in the following code snippet using the analysis report.

Analysis report:
{analysis}

Buggy code snippet:
{code_snippet}

Instructions:
- Output ONLY a unified diff patch start with: `diff --git a/filename b/filename`.
- Generate ONLY a valid patch in unified diff format (starting with "diff --u").
- Do not add explanations, plain text, markdown or comments.
- If you cannot generate a patch, output exactly an empty string ("").
- Do NOT output anything outside the diff.

"""
