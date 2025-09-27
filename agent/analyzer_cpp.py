import subprocess
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = Path(__file__).resolve().parent / "analysis_report_cpp.txt"
SNIPPET_FILE = Path(__file__).resolve().parent / "snippets" / "bug_snippets_cpp.txt"
SNIPPET_FILE.parent.mkdir(exist_ok=True)


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr


def analyze_cpp():
    cpp_repo = BASE_DIR / "cpp_project"
    print("[*] Running C++ analysis (cppcheck + optional clang-tidy)...")

    # Check for cppcheck availability early and provide a helpful message
    cppcheck_cmd = shutil.which("cppcheck")
    # On Windows, user might have cppcheck installed under Program Files but not on PATH
    if cppcheck_cmd is None:
        possible_paths = [
            Path("C:/Program Files/Cppcheck/cppcheck.exe"),
            Path("C:/Program Files (x86)/Cppcheck/cppcheck.exe"),
        ]
        for p in possible_paths:
            if p.exists():
                cppcheck_cmd = str(p)
                break

    if cppcheck_cmd is None:
        msg = "[!] 'cppcheck' not found in PATH or common install locations. Install cppcheck or add it to PATH."
        print(msg)
        return msg

    # cppcheck focus on warnings, performance, portability
    output1 = run_command(
        f'"{cppcheck_cmd}" --enable=warning,performance,portability --inconclusive --quiet --force . 2>&1',
        cwd=cpp_repo,
    )

    # clang-tidy (optional, if compile_commands.json exists)
    tidy_file = cpp_repo / "compile_commands.json"
    output2 = ""
    if tidy_file.exists():
        output2 = run_command("clang-tidy **/*.cpp -- -std=c++17", cwd=cpp_repo)

    return output1 + "\n" + output2


def extract_snippets(report_content):
    pattern = r"([^\s:]+\.cpp):(\d+):"
    matches = re.findall(pattern, report_content)
    print(f"[*] Found {len(matches)} C++ issues")

    snippets = []
    for file_path, line_str in matches[:20]:
        try:
            line_num = int(line_str)
            source_file = (BASE_DIR / file_path).resolve()
            if not source_file.exists():
                source_file = BASE_DIR / "cpp_project" / file_path

            if source_file.exists():
                lines = source_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                start = max(0, line_num - 5)
                end = min(len(lines), line_num + 5)
                snippet = "\n".join(lines[start:end])
                entry = f"--- {file_path}:{line_num} ---\n{snippet}\n"
                snippets.append(entry)
        except Exception as e:
            print(f"[!] Failed to extract snippet from {file_path}:{line_str} -> {e}")

    if snippets:
        SNIPPET_FILE.write_text("\n\n".join(snippets), encoding="utf-8")
        print(f"[+] C++ snippets saved to {SNIPPET_FILE}")


if __name__ == "__main__":
    report = analyze_cpp()
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"[+] C++ analysis saved to {REPORT_FILE}")
    extract_snippets(report)
