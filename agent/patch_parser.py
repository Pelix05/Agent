import re
from pathlib import Path


class PatchValidationError(Exception):
    pass


def looks_like_unified_diff(text: str) -> bool:
    """Basic checks for unified diff structure."""
    if not text or not isinstance(text, str):
        return False

    # Must contain git diff marker
    if "diff --git" not in text:
        return False

    # Must contain file change headers
    if not re.search(r"^\+\+\+\s", text, re.M):
        return False
    if not re.search(r"^---\s", text, re.M):
        return False

    return True


def extract_changed_files(diff_text: str):
    """Return a set of file paths modified by the diff (from diff --git headers)."""
    files = set()
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)", diff_text, re.M):
        files.add(m.group(2))
    return files


def validate_patch(diff_text: str, allowed_files=None):
    """Validate diff format and ensure files are allowed.

    allowed_files: optional iterable of file paths (relative) that patches may touch.
    Raises PatchValidationError on failure.
    """
    if not looks_like_unified_diff(diff_text):
        raise PatchValidationError("Not a valid unified diff: missing required headers")

    changed = extract_changed_files(diff_text)
    if allowed_files is not None:
        allowed = set(map(str, allowed_files))
        bad = [f for f in changed if f not in allowed]
        if bad:
            raise PatchValidationError(f"Patch modifies disallowed files: {bad}")

    return True
