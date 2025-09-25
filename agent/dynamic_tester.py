import os
import subprocess
from pathlib import Path
import shutil

# === Folder setup ===
BASE_DIR = Path(__file__).resolve().parent
PATCHES_DIR = BASE_DIR / "patches"
CPP_DIR = BASE_DIR.parent / "cpp_project"
PY_DIR = BASE_DIR.parent / "python_repo"
REPORT_FILE = BASE_DIR / "dynamic_report.md"

PATCH_FILE = PATCHES_DIR / "all_patches.diff"


def run_cmd(cmd, cwd=None):
    """Utility: run shell command & capture output"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def apply_patch(patch_file: Path, target_dir: Path):
    """Apply patch file to a repo (git apply)"""
    return run_cmd(["git", "apply", str(patch_file)], cwd=target_dir)


def revert_patch(patch_file: Path, target_dir: Path):
    """Revert applied patch (if failed)"""
    return run_cmd(["git", "apply", "-R", str(patch_file)], cwd=target_dir)


def test_cpp_project():
    """Compile and run C++ tests"""
    cpp_files = list(CPP_DIR.glob("*.cpp"))
    if not cpp_files:
        return False, "No C++ source files found."

    exe_file = CPP_DIR / "test_exec.exe"
    code, out = run_cmd(["g++", "-std=c++17", "-o", str(exe_file)] + [str(f) for f in cpp_files], cwd=CPP_DIR)
    if code != 0:
        return False, f"Compile error:\n{out}"

    code, out = run_cmd([str(exe_file)], cwd=CPP_DIR)
    return code == 0, out


def test_python_project():
    """Run pytest or unittest"""
    if not PY_DIR.exists():
        return False, "No Python repo found."

    # Prefer pytest, fallback to unittest
    if (PY_DIR / "tests").exists():
        code, out = run_cmd(["pytest", "-q"], cwd=PY_DIR)
    else:
        code, out = run_cmd(["python", "-m", "unittest", "discover"], cwd=PY_DIR)

    return code == 0, out


def run_dynamic_analysis():
    if not PATCH_FILE.exists():
        print("[!] No patch file found.")
        return

    results = []
    patches = PATCH_FILE.read_text(encoding="utf-8").split("=== PATCH")
    print(f"[*] Found {len(patches)-1} patches to test")

    for i, patch_block in enumerate(patches[1:], start=1):
        tmp_patch = PATCHES_DIR / f"_tmp_patch_{i}.diff"
        tmp_patch.write_text(patch_block, encoding="utf-8")

        print(f"\n🔧 Testing PATCH {i}...")

        # First try apply to C++ repo
        success, log = False, ""
        if CPP_DIR.exists():
            code, out = apply_patch(tmp_patch, CPP_DIR)
            if code == 0:
                success, log = test_cpp_project()
                if not success:
                    revert_patch(tmp_patch, CPP_DIR)
            else:
                log = f"Failed to apply to C++: {out}"

        # If not C++, try Python repo
        if not success and PY_DIR.exists():
            code, out = apply_patch(tmp_patch, PY_DIR)
            if code == 0:
                success, log = test_python_project()
                if not success:
                    revert_patch(tmp_patch, PY_DIR)
            else:
                log = f"Failed to apply to Python: {out}"

        status = "✅ Success" if success else "❌ Failed"
        results.append((i, status, log[:500]))  # truncate long logs

        # Clean up
        tmp_patch.unlink(missing_ok=True)

    # Write report
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# Dynamic Analysis Report\n\n")
        for i, status, log in results:
            f.write(f"## Patch {i}: {status}\n")
            f.write("```\n" + log.strip() + "\n```\n\n")

    print(f"\n[✅] Dynamic analysis finished. Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    run_dynamic_analysis()
