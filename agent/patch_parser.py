import re
from pathlib import Path


class PatchValidationError(Exception):
    pass


def parse_changed_files_from_report(report_text: str):
    """Extract file paths mentioned in the analysis report or snippets.

    This is a simple heuristic: find occurrences of paths like 'path/to/file.ext:line:'.
    Returns a set of normalized path-like strings.
    """
    pattern = r"([\w\-\\/. ]+\.[a-zA-Z0-9_]+):\d+:"
    matches = re.findall(pattern, report_text)
    files = set()
    for m in matches:
        # normalize backslashes
        files.add(Path(m.replace('\\', '/')).as_posix())
    return files


def validate_unified_diff(diff_text: str, allowed_files: set):
    """Validate the LLM output is a unified diff and only touches allowed files.

    Checks for presence of 'diff --git', at least one '---' and '+++',
    and that each changed file path exists in allowed_files (suffix match ok).
    """
    if 'diff --git' not in diff_text:
        raise PatchValidationError("Missing 'diff --git' header")
    if '--- ' not in diff_text or '+++ ' not in diff_text:
        raise PatchValidationError("Missing '---' or '+++' file markers")

    # find all file paths after diff --git a/... b/...
    git_headers = re.findall(r"diff --git a/(.+?) b/(.+)", diff_text)
    if not git_headers:
        raise PatchValidationError("No git header file paths found")

    changed = set()
    for a, b in git_headers:
        changed.add(a)

    normalized_allowed = set(allowed_files)
    for ch in changed:
        if not any(str(af).endswith(ch) or ch.endswith(str(af)) for af in normalized_allowed):
            raise PatchValidationError(f"Patch attempts to modify disallowed file: {ch}")

    return True


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print("Usage: patch_parser.py <report_file> <patch_file>")
        raise SystemExit(2)

    report = Path(sys.argv[1]).read_text(encoding='utf-8')
    patch = Path(sys.argv[2]).read_text(encoding='utf-8')
    allowed = parse_changed_files_from_report(report)
    try:
        ok = validate_unified_diff(patch, allowed)
        print("VALID")
    except PatchValidationError as e:
        print("INVALID:", e)
