import os
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
import importlib.util
import sys
import traceback

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = BASE_DIR / "dynamic_analysis_report.txt"
CPP_REPO = BASE_DIR / "cpp_project" / "puzzle-2"
PY_REPO = BASE_DIR / "python_repo"
PUZZLE_CHALLENGE = PY_REPO / "puzzle-challenge"

# Add puzzle-challenge to sys.path for imports
sys.path.insert(0, str(PUZZLE_CHALLENGE))

# === Helper Functions ===
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
def apply_patches_from_dir(target_repo, patch_dir, report_lines):
    patch_files = sorted(patch_dir.glob("patch_*.diff"))
    if not patch_files:
        report_lines.append(f"[!] No patch files found in {patch_dir}\n")
        return

    for patch_file in patch_files:
        report_lines.append(f"\n[*] Applying {patch_file} ...")
        try:
            patch_text = patch_file.read_text(encoding="utf-8")
        except Exception as e:
            report_lines.append(f"[!] Failed to read patch: {e}")
            continue

        success, output = run_command(
            ["git", "apply", "-"], cwd=target_repo, input_text=patch_text
        )
        if success:
            report_lines.append(f"[+] Patch {patch_file.name} applied successfully.")
        else:
            report_lines.append(f"[!] Patch {patch_file.name} failed:\n{output}")

# === C++ TESTER ===
def run_cpp_tests(report_lines):
    cpp_files = list(CPP_REPO.rglob("*.cpp"))
    if not cpp_files:
        report_lines.append("[!] No C++ files found to compile.")
        return

    exe_name = "main.exe" if os.name == "nt" else "main"
    compile_cmd = (
        f"g++ -std=c++17 -Wall -Wextra -fsanitize=address -o {exe_name} "
        + " ".join(str(f) for f in cpp_files)
    )

    success, output = run_command(compile_cmd, cwd=CPP_REPO)
    report_lines.append("\n=== BUILD & RUN TESTS (C++) ===")
    if not success:
        report_lines.append(f"[!] Compilation failed:\n{output}")
        return

    run_cmd = exe_name if os.name == "nt" else f"./{exe_name}"
    success, output = run_command(run_cmd, cwd=CPP_REPO)
    if not success:
        report_lines.append(f"[!] Runtime failed:\n{output}")
    else:
        report_lines.append(f"[+] Program executed successfully:\n{output}")

# === MOCK RESOURCES ===
def ensure_mock_resources():
    for folder in ["graphics", "sounds", "music"]:
        path = PUZZLE_CHALLENGE / "resources" / folder
        path.mkdir(parents=True, exist_ok=True)

# === PYTHON TESTER ===
def run_py_bug_tests(report_lines):
    bug_snippets = [
        ("puzzle_piece", "close_enough"),
        ("labels", "render_text"),
        ("puzzle", "get_event"),
    ]

    # Ensure resource folders exist to prevent FileNotFoundError
    ensure_mock_resources()

    for module_name, func_name in bug_snippets:
        report_lines.append(f"[*] Testing {module_name}.{func_name} ...")
        try:
            module_path = PUZZLE_CHALLENGE / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            func = getattr(mod, func_name, None)
            if func:
                if func_name == "close_enough":
                    result = func(10, 15)
                    report_lines.append(f"    -> {func_name} returned {result}")
                else:
                    report_lines.append(f"    -> {func_name} exists (manual verification needed)")
            else:
                report_lines.append(f"    [!] {func_name} not found in module")
        except Exception as e:
            report_lines.append(f"    [!] Error running {func_name}:\n{traceback.format_exc()}")

# === MAIN ===
def main():
    parser = argparse.ArgumentParser(description="Dynamic Tester")
    parser.add_argument("--cpp", action="store_true", help="Run C++ dynamic tests")
    parser.add_argument("--py", action="store_true", help="Run Python dynamic tests")
    args = parser.parse_args()

    report_lines = []
    report_lines.append("# Dynamic Analysis Report")
    report_lines.append(f"Date: {datetime.now()}\n")

    agent_dir = Path(__file__).resolve().parent
    patches_cpp = agent_dir / "patches" / "patches_cpp_fixed"
    patches_py = agent_dir / "patches_py_fixed"

    if args.cpp:
        report_lines.append(f"[*] Applying patches to CPP repo: {CPP_REPO}")
        apply_patches_from_dir(CPP_REPO, patches_cpp, report_lines)
        run_cpp_tests(report_lines)

    elif args.py:
        report_lines.append(f"[*] Applying patches to Python repo: {PY_REPO}")
        apply_patches_from_dir(PY_REPO, patches_py, report_lines)
        run_py_bug_tests(report_lines)

    else:
        report_lines.append("[!] No language specified. Use --cpp or --py")

    final_report = "\n".join(report_lines)
    REPORT_FILE.write_text(final_report, encoding="utf-8")
    print(final_report)
    print(f"\n[+] Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    main()
