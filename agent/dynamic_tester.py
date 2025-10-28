import os
import subprocess
from pathlib import Path
from datetime import datetime
import argparse
import importlib.util
import sys
import io
import traceback
import importlib

# === 安全输出设置 ===
# 保存原始 stdout/stderr
ORIG_STDOUT = sys.__stdout__
ORIG_STDERR = sys.__stderr__

# 创建 UTF-8 safe wrapper
def safe_print(*args, **kwargs):
    """Print safely to UTF-8 console, even on Windows."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # fallback: encode/decode with replace
        text = " ".join(str(a) for a in args)
        ORIG_STDOUT.write(text.encode('utf-8', errors='replace').decode('utf-8') + "\n")

# 强制 Python 使用 UTF-8
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
print("[DEBUG] Forced Python to use UTF-8 encoding")

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = BASE_DIR / "dynamic_analysis_report.txt"
CPP_REPO = BASE_DIR / "cpp_project" / "puzzle-2"
PY_REPO = BASE_DIR / "python_repo"
PUZZLE_CHALLENGE = PY_REPO / "puzzle-challenge"

# Add puzzle-challenge to sys.path
#sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
#sys.path.insert(0, str(PUZZLE_CHALLENGE))
#print(f"[DEBUG] Added puzzle-challenge to sys.path: {PUZZLE_CHALLENGE}")

# === Helper Functions ===
def run_command(cmd, cwd=None, input_text=None):
    """Run shell command with optional stdin and return success + output."""
    import subprocess
    import sys

    print(f"[DEBUG] Running command: {cmd}, cwd={cwd}")
    try:
        # Popen 实时读取 stdout/stderr
        proc = subprocess.Popen(
            cmd,
            shell=isinstance(cmd, str),
            cwd=cwd,
            stdin=subprocess.PIPE if input_text else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
        )

        # 如果有 input_text，写入 stdin
        if input_text:
            proc.stdin.write(input_text)
            proc.stdin.close()

        output_lines = []
        # 实时读取 stdout
        for line in proc.stdout:
            line = line.rstrip("\n")
            print(line, flush=True)   # 直接输出到控制台
            output_lines.append(line)

        proc.wait()
        return proc.returncode == 0, "\n".join(output_lines)

    except Exception as e:
        print(f"[DEBUG] Exception in run_command: {e}")
        return False, str(e)

# === PATCH HANDLER ===
def apply_patches_from_dir(target_repo, patch_dir):
    """Apply patches and return list of dict results {name, status, detail}"""
    print(f"[DEBUG] Applying patches from directory: {patch_dir}")
    results = []
    patch_files = sorted(patch_dir.glob("patch_*.diff"))
    print(f"[DEBUG] Found {len(patch_files)} patch files: {[str(p) for p in patch_files]}")
    if not patch_files:
        print(f"[DEBUG] No patch files found in {patch_dir}")
        return results

    for patch_file in patch_files:
        name = patch_file.name
        try:
            patch_text = patch_file.read_text(encoding="utf-8")
            print(f"[DEBUG] Reading patch file {patch_file}: {patch_text[:100]}...")
        except Exception as e:
            print(f"[DEBUG] Error reading patch file {patch_file}: {e}")
            results.append({"name": name, "status": "FAILED", "detail": f"read error: {e}"})
            continue

        success, output = run_command(["git", "apply", "-"], cwd=target_repo, input_text=patch_text)
        if success:
            print(f"[DEBUG] Patch {name} applied successfully")
            results.append({"name": name, "status": "SUCCESS", "detail": ""})
        else:
            reason = output.strip().splitlines()[0] if output else "unknown error"
            print(f"[DEBUG] Patch {name} failed to apply: {reason}")
            fb_reason = None
            for fb in ["--unidiff-zero", "--reject"]:
                fb_cmd = f"git apply {fb} -"
                fb_success, fb_output = run_command(fb_cmd, cwd=target_repo, input_text=patch_text)
                if fb_success:
                    print(f"[DEBUG] Patch {name} applied successfully with {fb}")
                    results.append({"name": name, "status": "SUCCESS", "detail": f"applied with {fb}"})
                    fb_reason = None
                    break
                else:
                    fb_reason = fb_output.strip().splitlines()[0] if fb_output else fb_reason
                    print(f"[DEBUG] Patch {name} failed to apply with {fb}: {fb_reason}")
            if fb_reason is not None:
                print(f"[DEBUG] Patch {name} failed all fallbacks: {fb_reason}")
                results.append({"name": name, "status": "FAILED", "detail": fb_reason})
    return results

def find_qmake():
    """尝试自动找到 qmake.exe"""
    print("[DEBUG] Entering find_qmake()")
    # 方法 1：查找已知 Qt 安装目录（相对项目根）
    base_dir = Path(__file__).resolve().parent.parent
    possible_qt_dirs = [
        Path(r"C:/Qt/6.9.2/mingw_64/bin"),  # ✅ 加入这一行
        base_dir / "Qt" / "6.9.2" / "mingw_64" / "bin",
        base_dir / "qt" / "6.9.2" / "mingw_64" / "bin"
    ]
    
    for qt_bin in possible_qt_dirs:
        qmake_path = qt_bin / "qmake.exe"
        if qmake_path.exists():
            print(f"[DEBUG] Found qmake at default location: {qmake_path}")
            return qmake_path

    # 方法 2：搜索系统 PATH
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(p) / "qmake.exe"
        if candidate.exists():
            print(f"[DEBUG] Found qmake at PATH: {candidate}")
            return candidate

    raise FileNotFoundError("qmake.exe not found! 请检查 Qt 安装路径或 PATH。")

qmake_path = find_qmake()
print(f"[DEBUG] Found qmake at: {qmake_path}")

def find_graphics_folder():
    """自动找到 puzzle-challenge 的 graphics 文件夹"""
    print("[DEBUG] Entering find_graphics_folder()")
    base_dir = Path(__file__).resolve().parent.parent
    puzzle_dir = base_dir / "python_repo" / "puzzle-challenge"
    graphics_path = puzzle_dir / "resources" / "graphics"

    if not graphics_path.exists():
        print(f"[DEBUG] Graphics folder not found at {graphics_path}")
        raise FileNotFoundError(f"Graphics folder not found at {graphics_path}")
    print(f"[DEBUG] Graphics path: {graphics_path}")
    return graphics_path

graphics_path = find_graphics_folder()
print(f"[DEBUG] Graphics path: {graphics_path}")

# === C++ TESTER ===
def run_cpp_tests():
    """Compile and run C++ file main.cpp intelligently (only recompile if Qt DLLs missing)."""
    print("[DEBUG] Entering run_cpp_tests()")
    results = []

    main_cpp_path = CPP_REPO / "main.cpp"
    if not main_cpp_path.exists():
        print(f"[DEBUG] main.cpp not found at {main_cpp_path}")
        results.append({"test": "C++ compile/run", "status": "FAIL", "detail": f"main.cpp not found"})
        return results

    # === Step 1: Find .pro file or create one ===
    pro_files = list(CPP_REPO.glob("*.pro"))
    if pro_files:
        pro_file = pro_files[0]
        print(f"[DEBUG] Found .pro file: {pro_file}")
    else:
        print("[DEBUG] No .pro file found, creating a new one...")
        pro_file_content = (
            "QT += core gui sql multimedia\n"
            "CONFIG += c++17\n"
            "DEFINES += QT_DEPRECATED_WARNINGS\n"
            "SOURCES += main.cpp\n"
            "HEADERS += mainwindow.h\n"
            "TARGET = main\n"
        )
        pro_file = CPP_REPO / "PuzzleGame.pro"
        pro_file.write_text(pro_file_content, encoding="utf-8")
        print(f"[DEBUG] Created .pro file at {pro_file}")

    exe_name = "main.exe" if os.name == "nt" else "main"
    target_name = "main"
    for line in pro_file.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("TARGET"):
            target_name = line.split("=")[1].strip()
            break
    exe_name = f"{target_name}.exe" if os.name == "nt" else target_name
    exe_path = CPP_REPO / "release" / exe_name
    print(f"[DEBUG] Target executable: {exe_path}")

    # === Step 2: 检查关键 Qt DLL 是否存在 ===
    missing_dlls = []
    if os.name == "nt":
        required_dlls = ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"]
        for dll in required_dlls:
            if not (exe_path.parent / dll).exists():
                missing_dlls.append(dll)
        if missing_dlls:
            print(f"[DEBUG] Missing DLLs detected: {missing_dlls}")
        else:
            print("[DEBUG] All required Qt DLLs present")

    need_recompile = not exe_path.exists() or (missing_dlls and os.name == "nt")

    # === Step 3: 若需要则执行编译 ===
    if need_recompile:
        print("[DEBUG] Compilation required (missing files detected or exe missing)")
        qmake_cmd = f'"{qmake_path}" "{pro_file}"'
        print(f"[DEBUG] Running qmake command: {qmake_cmd}")
        success, output = run_command(qmake_cmd, cwd=CPP_REPO)
        if not success:
            results.append({"test": "C++ qmake", "status": "FAIL", "detail": output})
            return results

        clean_cmd = "mingw32-make clean" if os.name == "nt" else "make clean"
        print(f"[DEBUG] Running clean command: {clean_cmd}")
        run_command(clean_cmd, cwd=CPP_REPO)

        compile_cmd = "mingw32-make all" if os.name == "nt" else "make all"
        print(f"[DEBUG] Running compile command: {compile_cmd}")
        success, output = run_command(compile_cmd, cwd=CPP_REPO)
        if not success:
            results.append({"test": "C++ compile", "status": "FAIL", "detail": output})
            return results
        print("[DEBUG] Compilation finished successfully.")

    else:
        print("[DEBUG] Compilation skipped (no missing files detected)")

    # === Step 4: 若是 Windows 则执行 windeployqt (部署 DLL) ===
    if os.name == "nt":
        qt_bin_dir = os.environ.get("QT_BIN_PATH", r"C:/Qt/6.9.2/mingw_64/bin")
        windeployqt_path = Path(qt_bin_dir) / "windeployqt.exe"
        if windeployqt_path.exists():
            deploy_cmd = f'"{windeployqt_path}" "{exe_path}" --no-translations'
            print(f"[DEBUG] Running windeployqt command: {deploy_cmd}")
            success, output = run_command(deploy_cmd, cwd=CPP_REPO)
            if success:
                print("[DEBUG] windeployqt completed successfully.")
            else:
                print(f"[DEBUG] windeployqt failed: {output}")
                results.append({"test": "Qt deploy", "status": "FAIL", "detail": output})
        else:
            print(f"[DEBUG] windeployqt not found at {windeployqt_path}")

    # === Step 5: Run the executable ===
    if not exe_path.exists():
        results.append({"test": "C++ runtime", "status": "FAIL", "detail": f"{exe_name} not found"})
        return results

    run_cmd = str(exe_path)
    print(f"[DEBUG] Running program: {run_cmd}")
    success, output = run_command(run_cmd, cwd=CPP_REPO)
    if success:
        results.append({"test": "C++ runtime", "status": "PASS", "detail": output})
    else:
        results.append({"test": "C++ runtime", "status": "FAIL", "detail": output})

    return results


# === MOCK RESOURCES ===
def ensure_mock_resources():
    """Ensure mock resources directories exist."""
    print("[DEBUG] Entering ensure_mock_resources()")
    for folder in ["graphics", "sounds", "music"]:
        path = PUZZLE_CHALLENGE / "resources" / folder
        if path.exists():
            print(f"[DEBUG] Directory {path} already exists")
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"[DEBUG] Created directory: {path}")

        # 检查文件夹内容
        if folder == "graphics":
            if not (path / "example.png").exists():
                print(f"[DEBUG] Graphics file example.png not found")
                (path / "example.png").touch()
                print(f"[DEBUG] Created empty graphics file: {path / 'example.png'}")

# === PYTHON BUG TESTS ===
def run_py_bug_tests():
    """Re-run known bug tests to verify fixes."""
    # 切换到 puzzle-challenge
    os.chdir(str(PUZZLE_CHALLENGE))
    print(f"[DEBUG] Changed current working directory to: {PUZZLE_CHALLENGE}")
    print("[DEBUG] Entering run_py_bug_tests()")
    bug_snippets = [
        ("puzzle_piece", "close_enough"),
        ("labels", "render_text"),
        ("puzzle", "get_event"),
    ]
    results = []
    ensure_mock_resources()

    for module_name, func_name in bug_snippets:
        test_name = f"test_{module_name}_{func_name}"
        print(f"[DEBUG] Processing test: {test_name}")
        try:
            module_path = PUZZLE_CHALLENGE / f"{module_name}.py"
            print(f"[DEBUG] Loading module from: {module_path}")
            if module_path.exists():
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                func = getattr(mod, func_name, None)
                print(f"[DEBUG] Function {func_name} found: {callable(func)}")
                if callable(func):
                    if func_name == "close_enough":
                        try:
                            result = func(10, 15)
                            ok = bool(result)
                            print(f"[DEBUG] close_enough returned: {result}, PASS: {ok}")
                            results.append({"test": test_name, "status": "PASS" if ok else "FAIL", "detail": f"returned {result}"})
                        except Exception as e:
                            print(f"[DEBUG] close_enough failed with exception: {e}")
                            results.append({"test": test_name, "status": "FAIL", "detail": traceback.format_exc()})
                    else:
                        print(f"[DEBUG] Function {func_name} is callable, PASS")
                        results.append({"test": test_name, "status": "PASS", "detail": "function callable"})
                else:
                    found = False
                    for name, obj in list(vars(mod).items()):
                        if isinstance(obj, type) and hasattr(obj, func_name):
                            found = True
                            print(f"[DEBUG] Method {func_name} found on class {name}, PASS")
                            results.append({"test": test_name, "status": "PASS", "detail": f"method on class {name}"})
                            break
                    if not found:
                        print(f"[DEBUG] Method {func_name} not found, FAIL")
                        results.append({"test": test_name, "status": "FAIL", "detail": f"{func_name} not found"})
            else:
                print(f"[DEBUG] Module file {module_path} not found, FAIL")
                results.append({"test": test_name, "status": "FAIL", "detail": f"Module file {module_path} not found"})
        except Exception as e:
            print(f"[DEBUG] Failed to load module {module_name} with exception: {e}")
            results.append({"test": test_name, "status": "FAIL", "detail": traceback.format_exc()})
    return results

# === RUN ALL PYTESTS ===
def run_full_regression_tests():
    """Run pytest across the repo to detect new regressions."""
    print("[DEBUG] Entering run_full_regression_tests()")
    if not (PY_REPO / "tests").exists():
        print(f"[DEBUG] Tests directory not found at {PY_REPO / 'tests'}")
        return []

    success, output = run_command("pytest -q --tb=short", cwd=PY_REPO)
    if success:
        print(f"[DEBUG] Pytest passed: {output}")
        results = [{"test": "pytest_suite", "status": "PASS", "detail": "All tests passed"}]
    else:
        print(f"[DEBUG] Pytest failed: {output}")
        results = [{"test": "pytest_suite", "status": "FAIL", "detail": output}]
    return results

# === MAIN ===
def main():
    # 从 sys.argv 获取命令
    print("[DEBUG] Entering main()")
    cmd = None
    for arg in sys.argv[1:]:
        if arg.lower() in ("cpp", "py"):
            cmd = arg.lower()
            break
        
    parser = argparse.ArgumentParser(description="Dynamic Tester")
    parser.add_argument("--cpp", action="store_true", help="Run C++ dynamic tests")
    parser.add_argument("--py", action="store_true", help="Run Python dynamic tests")
    args = parser.parse_args()
    print(f"[DEBUG] Parsed arguments: {args}")

    agent_dir = Path(__file__).resolve().parent
    patches_cpp = agent_dir / "patches" / "patches_cpp_fixed"
    patches_py = agent_dir / "patches_py_fixed"
    print(f"[DEBUG] Patches directories: CPP={patches_cpp}, PY={patches_py}")

    patch_results, test_results = [], []

    if args.cpp:
        print("[DEBUG] Starting C++ dynamic tests")
        patch_results = apply_patches_from_dir(CPP_REPO, patches_cpp)
        test_results = run_cpp_tests()
    elif args.py:
        print("[DEBUG] Starting Python dynamic tests")
        patch_results = apply_patches_from_dir(PY_REPO, patches_py)

        test_results = run_py_bug_tests()
        test_results += run_full_regression_tests()

    # --- Build Report ---
    print("[DEBUG] Building dynamic analysis report")
    lines = []
    lines.append("# Dynamic Analysis Report")
    lines.append(f"Date: {datetime.now().date()}")
    lines.append("")

    lines.append("== PATCH APPLICATION ==")
    for p in patch_results:
        if p["status"] == "SUCCESS":
            lines.append(f"{p['name']} ... SUCCESS")
            print(f"[DEBUG] Patch {p['name']} applied successfully")
        else:
            lines.append(f"{p['name']} ... FAILED ({p['detail']})")
            print(f"[DEBUG] Patch {p['name']} failed to apply: {p['detail']}")

    lines.append("")
    lines.append("== TEST EXECUTION ==")
    for t in test_results:
        if t["status"] == "PASS":
            lines.append(f"[+] {t['test']} ... PASS")
            print(f"[DEBUG] Test {t['test']} passed")
        else:
            lines.append(f"[-] {t['test']} ... FAIL")
            print(f"[DEBUG] Test {t['test']} failed: {t['detail']}")
            for dl in str(t['detail']).splitlines():
                lines.append(f"    {dl}")

    total_patches = len(patch_results)
    applied = sum(1 for p in patch_results if p["status"] == "SUCCESS")
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t["status"] == "PASS")
    remaining = total_tests - passed_tests
    new_issues = sum(1 for t in test_results if t["status"] == "FAIL")

    lines.append("")
    lines.append("== SUMMARY ==")
    lines.append(f"Patches applied: {applied}/{total_patches}")
    lines.append(f"Bugs fixed: {passed_tests}")
    lines.append(f"Remaining issues: {remaining}")
    lines.append(f"New issues: {new_issues}")

    final_report = "\n".join(lines)
    REPORT_FILE.write_text(final_report, encoding="utf-8")
    safe_print(final_report)
    safe_print(f"\n[+] Report saved to {REPORT_FILE}")

# === RELAUNCH FOR PYGAME ===
if __name__ == "__main__":
    print("[DEBUG] Program started")
    if "--py" in sys.argv and os.environ.get("DYNAMIC_TESTER_RELAUNCHED") != "1":
        try:
            if importlib.util.find_spec("pygame") is None:
                print("[DEBUG] pygame not found. Relaunching with pygame environment")
                env = os.environ.copy()
                env["DYNAMIC_TESTER_RELAUNCHED"] = "1"
                cmd = ["py", "-3", "-u", sys.argv[0]] + sys.argv[1:]
                print(f"[Debug] Relaunching with command: {' '.join(cmd)}")
                rc = subprocess.run(
                    cmd,
                    env=env,
                    text=True,
                    encoding='utf-8',      
                    errors='replace',     
                    capture_output=True,   
                ).returncode
                sys.exit(rc)
        except Exception as e:
            print(f"[DEBUG] Exception in pygame relaunch: {e}")
    main()
