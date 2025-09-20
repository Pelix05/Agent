BUG_FIX_PROMPT = """
You are an expert software engineer assistant.
Below is a problematic code snippet and its corresponding error analysis from static analysis tools.

--- CODE SNIPPET ---
{code_snippet}

--- ERROR ANALYSIS ---
{analysis}

Your task:
1. **Identify the Bug:** Concisely describe the root cause of the bug within 2 sentences.
2. **Show the Fix:** Provide a corrected version of the code snippet.
3. **Explain the Fix:** Briefly explain why your solution resolves the issue within 1 sentence.
4. Don't change anything outside the snippet.

Ensure the fix is minimal, targeted, and maintains the original code's intent.
"""