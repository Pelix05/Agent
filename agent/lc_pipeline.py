import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from prompts import BUG_FIX_PROMPT

# === Load env ===
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
QWEN_KEY = os.getenv("QWEN_API_KEY")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")

# === LangChain Clients ===
gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=GEMINI_KEY,
) if GEMINI_KEY else None

qwen_llm = ChatOpenAI(
    api_key=QWEN_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen2.5-7b-instruct"
) if QWEN_KEY else None

ollama_llm = ChatOllama(
    model=LOCAL_MODEL,
    temperature=0.3,
)

# === Folder setup ===
BASE_DIR = Path(__file__).resolve().parent
SNIPPETS_DIR = BASE_DIR / "snippets"
PATCHES_DIR = BASE_DIR / "patches"
PATCHES_DIR.mkdir(exist_ok=True)

REPORT_CPP = BASE_DIR / "analysis_report_cpp.txt"
REPORT_PY = BASE_DIR / "analysis_report_py.txt"
SNIPPET_CPP = SNIPPETS_DIR / "bug_snippets_cpp.txt"
SNIPPET_PY = SNIPPETS_DIR / "bug_snippets_py.txt"
PATCH_FILE = PATCHES_DIR / "all_patches.diff"


def ask_llm(prompt: str) -> str:
    """Try Gemini → Qwen → Ollama with fallback"""
    if gemini_llm:
        try:
            resp = gemini_llm.invoke([HumanMessage(content=prompt)])
            if "diff --git" in resp.content:
                print("[+] Patch from Gemini")
                return resp.content
            else:
                print("[!] Gemini invalid format, fallback...")
        except Exception as e:
            print(f"[!] Gemini failed: {e} → fallback to Qwen...")

    if qwen_llm:
        try:
            resp = qwen_llm.invoke([HumanMessage(content=prompt)])
            if "diff --git" in resp.content:
                print("[+] Patch from Qwen")
                return resp.content
            else:
                print("[!] Qwen invalid format, fallback...")
        except Exception as e:
            print(f"[!] Qwen failed: {e} → fallback to Ollama...")

    try:
        resp = ollama_llm.invoke([HumanMessage(content=prompt)])
        return resp.content
    except Exception as e:
        return f"[!] Ollama failed: {e}"


def run_static_analysis(lang="cpp"):
    """Run static analysis for C++ or Python"""
    if lang == "cpp":
        print("🔍 Running static analysis for C++...")
        subprocess.run(["python", str(BASE_DIR / "analyzer_cpp.py")])
    elif lang == "py":
        print("🔍 Running static analysis for Python...")
        subprocess.run(["python", str(BASE_DIR / "analyzer_py.py")])


def run_patch_pipeline(report_file, snippet_file):
    """Generate patches using snippets + report"""
    if not report_file.exists() or not snippet_file.exists():
        print("[!] Report or snippet not found. Run static analysis first.")
        return

    report = report_file.read_text(encoding="utf-8")
    snippets = snippet_file.read_text(encoding="utf-8").split("--- ")

    print(f"[*] Found {len(snippets)-1} snippets to process")

    with open(PATCH_FILE, "w", encoding="utf-8") as f:
        for i, snippet in enumerate(snippets[1:], start=1):
            print(f"🔧 Processing snippet {i}...")
            prompt = BUG_FIX_PROMPT.format(
                code_snippet=snippet.strip(),
                analysis=report
            )
            patch = ask_llm(prompt)

            if "diff --git" in patch:
                f.write(f"\n\n=== PATCH {i} ===\n")
                f.write(patch.strip())
                f.write("\n" + "="*50 + "\n")
                print(f"[+] Patch {i} appended to {PATCH_FILE}")
            else:
                print(f"[!] Skipping snippet {i}, invalid diff format")


def run_dynamic_test():
    print("⚡ Running dynamic tester...")
    subprocess.run(["python", str(BASE_DIR / "dynamic_tester.py")])


def main_menu():
    while True:
        print("\nOptions:")
        print("1. Static Analysis (C++)")
        print("2. Static Analysis (Python)")
        print("3. Generate Patch (C++)")
        print("4. Generate Patch (Python)")
        print("5. Run Dynamic Tester")
        print("6. Exit")
        choice = input("👉 Pilihanmu: ").strip()

        if choice == "1":
            run_static_analysis("cpp")
        elif choice == "2":
            run_static_analysis("py")
        elif choice == "3":
            run_patch_pipeline(REPORT_CPP, SNIPPET_CPP)
        elif choice == "4":
            run_patch_pipeline(REPORT_PY, SNIPPET_PY)
        elif choice == "5":
            run_dynamic_test()
        elif choice == "6":
            print("👋 Exiting...")
            break
        else:
            print("[!] Invalid choice")


if __name__ == "__main__":
    print("🤖 AI Agent ready! Choose an action:")
    main_menu()
