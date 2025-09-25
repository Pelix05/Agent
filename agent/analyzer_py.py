import subprocess
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_FILE = Path(__file__).resolve().parent / "analysis_report_py.txt"
SNIPPET_FILE = Path(__file__).resolve().parent / "snippets" / "bug_snippets_py.txt"
SNIPPET_FILE.parent.mkdir(exist_ok=True)


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.stdout + result.stderr


def analyze_python():
    python_repo = BASE_DIR / "python_repo"
    print("[*] Running Python analysis (pylint + flake8 + bandit)...")

    # pylint: only errors and fatal (disable refactor, convention, warning)
    output1 = run_command(
        "pylint --disable=R,C,W --enable=E,F --score=n --exit-zero --recursive=y .",
        cwd=python_repo,
    )

    # flake8: focus on syntax error, undefined name, unused import
    output2 = run_command(
        "flake8 --select=E9,F63,F7,F82 --show-source --statistics .",
        cwd=python_repo,
    )

    # bandit: security issue
    output3 = run_command("bandit -r .", cwd=python_repo)

    return output1 + "\n" + output2 + "\n" + output3


def extract_snippets(report_content):
    pattern = r"([^\s:]+\.py):(\d+):"
    matches = re.findall(pattern, report_content)
    print(f"[*] Found {len(matches)} Python issues")

    snippets = []
    for file_path, line_str in matches[:20]:
        try:
            line_num = int(line_str)
            source_file = (BASE_DIR / file_path).resolve()
            if not source_file.exists():
                source_file = BASE_DIR / "python_repo" / file_path

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
        print(f"[+] Python snippets saved to {SNIPPET_FILE}")


if __name__ == "__main__":
    report = analyze_python()
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"[+] Python analysis saved to {REPORT_FILE}")
    extract_snippets(report)
