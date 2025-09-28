import os
import subprocess
from pathlib import Path
from datetime import datetime
import argparse

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent.parent
PATCH_FILE = BASE_DIR / "agent" / "patches" / "all_patches.diff"
REPORT_FILE = BASE_DIR / "dynamic_analysis_report.txt"
CPP_REPO = BASE_DIR / "cpp_project" / "puzzle-2"
PY_REPO = BASE_DIR / "python_repo"


def run_command(cmd, cwd=None, input_text=None):
    """Run shell command, optionally with stdin text."""
    try:
        result = subprocess.run(
            cmd,
            shell=isinstance(cmd, str),
            input=input_text,
            text=True,
            cwd=cwd,
            capture_output=True,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


# === PATCH HANDLER ===
def apply_patches(target_repo, report_lines):
    """Apply patches from all_patches.diff one by one. Skip invalid patches."""
    if not PATCH_FILE.exists():
        report_lines.append("[!] No patch file found.\n")
        return

    current_patch = []
    patch_idx = 0

    with open(PATCH_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("diff --git"):
                if current_patch:
                    patch_idx += 1
                    apply_single_patch(patch_idx, current_patch, target_repo, report_lines)
                    current_patch = []
            if line.strip() and not line.startswith("==="):  # skip dekorasi
                current_patch.append(line)

        if current_patch:
            patch_idx += 1
            apply_single_patch(patch_idx, current_patch, target_repo, report_lines)


def apply_single_patch(idx, patch_lines, repo, report_lines):
    """Apply one patch directly via stdin (no temp file)."""
    patch_text = "".join(patch_lines)
    success, output = run_command(["git", "apply", "-"], cwd=repo, input_text=patch_text)

    report_lines.append(f"\n=== PATCH {idx} ===")
    if success:
        report_lines.append("[+] Patch applied successfully.\n")
    else:
        report_lines.append(f"[!] Patch failed to apply:\n{output.strip()}\n")


# === CPP TESTER ===
def run_cpp_tests(report_lines):
    cpp_files = list(CPP_REPO.rglob("*.cpp"))
    if not cpp_files:
        report_lines.append("[!] No C++ files found to compile.\n")
        return

    exe_name = "main.exe" if os.name == "nt" else "main"
    compile_cmd = (
        f"g++ -std=c++17 -Wall -Wextra -fsanitize=address -o {exe_name} "
        + " ".join(str(f) for f in cpp_files)
    )

    success, output = run_command(compile_cmd, cwd=CPP_REPO)
    report_lines.append("\n=== BUILD & RUN TESTS (C++) ===")
    if not success:
        report_lines.append(f"[!] Compilation failed:\n{output}\n")
        return

    run_cmd = exe_name if os.name == "nt" else f"./{exe_name}"
    success, output = run_command(run_cmd, cwd=CPP_REPO)
    if not success:
        report_lines.append(f"[!] Runtime failed:\n{output}\n")
    else:
        report_lines.append(f"[+] Program executed successfully:\n{output}\n")


# === PY TESTER ===
def run_py_tests(report_lines):
    report_lines.append("\n=== RUN TESTS (Python) ===")
    if not PY_REPO.exists():
        report_lines.append("[!] Python repo not found.\n")
        return

    success, output = run_command("pytest -q", cwd=PY_REPO)
    if not success:
        report_lines.append(f"[!] Python tests failed:\n{output}\n")
    else:
        report_lines.append(f"[+] Python tests passed:\n{output}\n")


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(description="Dynamic Tester")
    parser.add_argument("--cpp", action="store_true", help="Run C++ dynamic tests")
    parser.add_argument("--py", action="store_true", help="Run Python dynamic tests")
    args = parser.parse_args()

    report_lines = []
    report_lines.append("# Dynamic Analysis Report")
    report_lines.append(f"Date: {datetime.now()}\n")

    if args.cpp:
        report_lines.append(f"[*] Applying patches to CPP repo: {CPP_REPO}")
        apply_patches(CPP_REPO, report_lines)
        run_cpp_tests(report_lines)

    elif args.py:
        report_lines.append(f"[*] Applying patches to Python repo: {PY_REPO}")
        apply_patches(PY_REPO, report_lines)
        run_py_tests(report_lines)

    else:
        report_lines.append("[!] No language specified. Use --cpp or --py")

    final_report = "\n".join(report_lines)
    REPORT_FILE.write_text(final_report, encoding="utf-8")
    print(final_report)
    print(f"\n[+] Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
