from pathlib import Path

REPORT_FILE = Path(__file__).resolve().parent / "analysis_report.txt"
SNIPPET_DIR = Path(__file__).resolve().parent / "snippets"

def load_report():
    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def load_snippets():
    snippets = []
    for file in SNIPPET_DIR.glob("*.cpp") | SNIPPET_DIR.glob("*.py"):
        with open(file, "r", encoding="utf-8") as f:
            snippets.append((file.name, f.read()))
    return snippets

if __name__ == "__main__":
    report = load_report()
    snippets = load_snippets()

    print("=== Static Analysis Report ===")
    print(report[:500])  # preview 500 chars

    print("\n=== Bug Snippets ===")
    for name, code in snippets:
        print(f"\nSnippet: {name}\n{code}")
