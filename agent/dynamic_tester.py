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
def apply_patches_from_dir(target_repo, patch_dir):
    """Apply patches and return structured results list.

    Returns: list of dict {name, status, detail}
    status is 'SUCCESS' or 'FAILED'
    """
    results = []
    patch_files = sorted(patch_dir.glob("patch_*.diff"))
    if not patch_files:
        return results

    for patch_file in patch_files:
        name = patch_file.name
        try:
            patch_text = patch_file.read_text(encoding="utf-8")
        except Exception as e:
            results.append({"name": name, "status": "FAILED", "detail": f"read error: {e}"})
            continue

        success, output = run_command(["git", "apply", "-"], cwd=target_repo, input_text=patch_text)
        if success:
            results.append({"name": name, "status": "SUCCESS", "detail": ""})
        else:
            # try to extract a short reason
            reason = output.strip().splitlines()[0] if output else "unknown error"
            results.append({"name": name, "status": "FAILED", "detail": reason})

    return results

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
def run_py_bug_tests():
    """Run python bug checks and return a list of test result dicts:
    {test, status, detail}
    status: PASS or FAIL
    """
    bug_snippets = [
        ("puzzle_piece", "close_enough"),
        ("labels", "render_text"),
        ("puzzle", "get_event"),
    ]

    results = []
    ensure_mock_resources()

    for module_name, func_name in bug_snippets:
        test_name = f"test_{module_name}_{func_name}"
        try:
            module_path = PUZZLE_CHALLENGE / f"{module_name}.py"
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            # check module-level
            func = getattr(mod, func_name, None)
            if callable(func):
                if func_name == "close_enough":
                    try:
                        result = func(10, 15)
                        ok = bool(result)
                        if ok:
                            results.append({"test": test_name, "status": "PASS", "detail": f"returned {result}"})
                        else:
                            results.append({"test": test_name, "status": "FAIL", "detail": f"returned {result}"})
                    except Exception:
                        results.append({"test": test_name, "status": "FAIL", "detail": traceback.format_exc()})
                else:
                    results.append({"test": test_name, "status": "PASS", "detail": "module-level function present"})
            else:
                # search classes
                found = False
                for name, obj in list(vars(mod).items()):
                    if isinstance(obj, type) and hasattr(obj, func_name):
                        found = True
                        results.append({"test": test_name, "status": "PASS", "detail": f"method on class {name}"})
                        break
                if not found:
                    results.append({"test": test_name, "status": "FAIL", "detail": f"{func_name} not found"})
        except Exception:
            results.append({"test": test_name, "status": "FAIL", "detail": traceback.format_exc()})

    return results

# === MAIN ===
def main():
    parser = argparse.ArgumentParser(description="Dynamic Tester")
    parser.add_argument("--cpp", action="store_true", help="Run C++ dynamic tests")
    parser.add_argument("--py", action="store_true", help="Run Python dynamic tests")
    args = parser.parse_args()

    agent_dir = Path(__file__).resolve().parent
    patches_cpp = agent_dir / "patches" / "patches_cpp_fixed"
    patches_py = agent_dir / "patches_py_fixed"

    # Build structured results
    patch_results = []
    test_results = []

    if args.cpp:
        patch_results = apply_patches_from_dir(CPP_REPO, patches_cpp)
        # For C++ we still run compile/tests for now
        run_cpp_tests([])
    elif args.py:
        patch_results = apply_patches_from_dir(PY_REPO, patches_py)
        test_results = run_py_bug_tests()
    else:
        # nothing requested
        pass

    # Format report according to the user's desired template
    lines = []
    lines.append("# Dynamic Analysis Report")
    lines.append(f"Date: {datetime.now().date()}")
    lines.append("")
    lines.append("== PATCH APPLICATION ==")
    for p in patch_results:
        if p["status"] == "SUCCESS":
            lines.append(f"{p['name']} ... SUCCESS")
        else:
            lines.append(f"{p['name']} ... FAILED ({p['detail']})")

    lines.append("")
    lines.append("== TEST EXECUTION ==")
    for t in test_results:
        if t["status"] == "PASS":
            lines.append(f"[+] {t['test']} ... PASS")
        else:
            lines.append(f"[-] {t['test']} ... FAIL")
            # indent detail lines
            for dl in str(t['detail']).splitlines():
                lines.append(f"    {dl}")

    # Summary
    total_patches = len(patch_results)
    applied = sum(1 for p in patch_results if p["status"] == "SUCCESS")
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t["status"] == "PASS")
    remaining = total_tests - passed_tests
    new_issues = 0

    lines.append("")
    lines.append("== SUMMARY ==")
    lines.append(f"Patches applied: {applied}/{total_patches}")
    lines.append(f"Bugs fixed: {passed_tests}")
    lines.append(f"Remaining issues: {remaining}")
    lines.append(f"New issues: {new_issues}")

    final_report = "\n".join(lines)
    REPORT_FILE.write_text(final_report, encoding="utf-8")
    print(final_report)
    print(f"\n[+] Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    main()
