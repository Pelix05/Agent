import subprocess
import re
from pathlib import Path

# Base directory of your project
BASE_DIR = Path(__file__).resolve().parent.parent

# Output files
REPORT_FILE = Path(__file__).resolve().parent / "analysis_report_cpp.txt"
SNIPPET_FILE = Path(__file__).resolve().parent / "snippets" / "bug_snippets_cpp.txt"
SNIPPET_FILE.parent.mkdir(exist_ok=True)

# Full path to cppcheck executable
CPP_CHECK_EXE = r"C:\Program Files\Cppcheck\cppcheck.exe"

def run_command(cmd, cwd=None):
    """Run a shell command and return combined stdout and stderr."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr

def analyze_cpp(run_cmd=run_command):
    """Run cppcheck on the repo and return the raw report string."""
    cpp_repo = BASE_DIR / "cpp_project"
    print("[*] Running C++ analysis (recursive)...")
    # Use full path to cppcheck
    cmd = f'"{CPP_CHECK_EXE}" --enable=all --quiet . 2>&1'
    return run_cmd(cmd, cwd=cpp_repo)

def extract_snippets(report_content):
    """Extract code snippets around the reported issues."""
    # Regex to find <file>.cpp:<line>:
    pattern = r"([^\s:]+\.cpp):(\d+):"
    matches = re.findall(pattern, report_content)
    print(f"[*] Found {len(matches)} C++ issues")

    snippets = []
    for file_path, line_str in matches[:20]:  # Limit to first 20 issues
        try:
            line_num = int(line_str)
            # Try relative to BASE_DIR first, then cpp_project folder
            source_file = BASE_DIR / file_path
            if not source_file.exists():
                source_file = BASE_DIR / "cpp_project" / file_path
            source_file = source_file.resolve() if source_file.exists() else source_file

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
