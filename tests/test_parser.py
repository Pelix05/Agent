import pytest
from agent.patch_parser import looks_like_unified_diff, validate_patch, PatchValidationError


VALID_DIFF = '''diff --git a/foo.txt b/foo.txt
--- a/foo.txt
+++ b/foo.txt
@@ -1 +1 @@
-old
+new
'''


def test_looks_like_unified_diff():
    assert looks_like_unified_diff(VALID_DIFF)


def test_validate_patch_ok():
    assert validate_patch(VALID_DIFF, allowed_files=['foo.txt']) is True


def test_validate_patch_disallowed():
    with pytest.raises(PatchValidationError):
        validate_patch(VALID_DIFF, allowed_files=['bar.txt'])
