"""
Small repair helper: try to clean sanitized patch files by removing stray non-diff lines
and ensuring reasonable hunk boundaries. This is conservative and non-destructive; it
writes repaired patches to patches/repaired_*.diff for manual inspection.

Usage: python agent/repair_patches.py --repo ../cpp_project/puzzle-2 --limit 3
"""
from pathlib import Path
import re
import subprocess
import argparse

PATCHES_DIR = Path(__file__).resolve().parent / "patches"


def run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return r.returncode == 0, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)


def repair_text(text: str) -> str:
    # Keep only lines that start with diff headers or typical hunk markers or context lines
    keep = []
    for line in text.splitlines():
        if line.startswith("diff --git") or line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ "):
            keep.append(line)
            continue
        if re.match(r"^@@ -\d+(,\d+)? \+\d+(,\d+)? @@", line):
            keep.append(line)
            continue
        if line.startswith(("+", "-", " ")):
            keep.append(line)
            continue
        # otherwise drop the line (likely prose or stray markers)
    repaired = "\n".join(keep)
    # Basic sanity: ensure starts with diff --git
    if not repaired.strip().startswith("diff --git"):
        return ""
    return repaired


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=str, required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    files = sorted(PATCHES_DIR.glob("sanitized_patch_*.diff"))[: args.limit]
    if not files:
        print("No sanitized_patch_*.diff files found in patches/")
        return

    for f in files:
        print(f"Processing {f.name}...")
        text = f.read_text(encoding="utf-8")
        repaired = repair_text(text)
        outp = PATCHES_DIR / f"repaired_{f.name}"
        outp.write_text(repaired, encoding="utf-8")
        print(f"Wrote {outp}")

        if not repaired:
            print("Repaired text empty, skipping git apply checks.")
            continue

        ok, out = run(["git", "apply", "--check", "-p1", str(outp)], cwd=repo)
        print("git apply --check -p1:", ok, out[:1000])
        if not ok:
            ok2, out2 = run(["git", "apply", "--check", "-p0", str(outp)], cwd=repo)
            print("git apply --check -p0:", ok2, out2[:1000])
            if ok2:
                ok3, out3 = run(["git", "apply", "-p0", str(outp)], cwd=repo)
                print("git apply -p0:", ok3, out3[:1000])
            else:
                print("Neither p1 nor p0 check succeeded.")
        else:
            ok3, out3 = run(["git", "apply", "-p1", str(outp)], cwd=repo)
            print("git apply -p1:", ok3, out3[:1000])


if __name__ == "__main__":
    main()
