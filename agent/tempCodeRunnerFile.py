import os
import re
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
    model="gemini-2.5-flash",
    google_api_key=GEMINI_KEY,
    temperature=0.1
) if GEMINI_KEY else None

qwen_llm = ChatOpenAI(
    api_key=QWEN_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    model="qwen1.5-7b-chat"
) if QWEN_KEY else None

ollama_llm = ChatOllama(model=LOCAL_MODEL, temperature=0.3)

# === Folder setup ===
BASE_DIR = Path(__file__).resolve().parent
SNIPPETS_DIR = BASE_DIR / "snippets"
PATCHES_DIR = BASE_DIR / "patches"
PATCHES_DIR.mkdir(exist_ok=True)

REPORT_CPP = BASE_DIR / "analysis_report_cpp.txt"
REPORT_PY = BASE_DIR / "analysis_report_py.txt"
SNIPPETS_CPP = SNIPPETS_DIR / "bug_snippets_cpp.txt"
SNIPPETS_PY = SNIPPETS_DIR / "bug_snippets_py.txt"
PATCH_FILE = PATCHES_DIR / "all_patches.diff"


def run_command(cmd, cwd=None):
    """Run shell command and print output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    print(result.stdout + result.stderr)


# === Fallback bug fixer ===
def ask_llm(prompt: str) -> str:
    """Minta patch ke Gemini → Qwen → Ollama (fallback)."""
    if gemini_llm:
        try:
            resp = gemini_llm.invoke([HumanMessage(content=prompt)])
            if "diff --git" in resp.content:
                print("[+] Patch from Gemini")
                return resp.content
        except Exception as e:
            print(f"[!] Gemini failed: {e}")

    if qwen_llm:
        try:
            resp = qwen_llm.invoke([HumanMessage(content=prompt)])
            if "diff --git" in resp.content:
                print("[+] Patch from Qwen")
                return resp.content
        except Exception as e:
            print(f"[!] Qwen failed: {e}")

    # Fallback ke Ollama
    resp = ollama_llm.invoke([HumanMessage(content=prompt)])
    return resp.content


def clean_patch_output(patch: str) -> str:
    """Bersihin output LLM jadi pure unified diff patch."""
    if not patch:
        return ""
    patch = re.sub(r"^```diff", "", patch, flags=re.MULTILINE).strip()
    patch = re.sub(r"^```", "", patch, flags=re.MULTILINE).strip()
    idx = patch.find("diff --git")
    if idx != -1:
        patch = patch[idx:]
    else:
        return ""
    return patch.strip()


def run_pipeline(report_file, snippet_file):
    """Jalankan patch pipeline dari hasil analisis & snippet."""
    if not report_file.exists() or not snippet_file.exists():
        print("[!] Report or snippet not found.")
        return

    report = report_file.read_text(encoding="utf-8")
    snippets = snippet_file.read_text(encoding="utf-8").split("--- ")

    print(f"[*] Found {len(snippets) - 1} snippets to process")

    with open(PATCH_FILE, "w", encoding="utf-8") as f:
        for i, snippet in enumerate(snippets[1:], start=1):
            print(f"🔧 Processing snippet {i}...")
            prompt = BUG_FIX_PROMPT.format(
                code_snippet=snippet.strip(),
                analysis=report
            )
            raw_patch = ask_llm(prompt)
            patch = clean_patch_output(raw_patch)

            if patch:
                f.write(f"\n\n=== PATCH {i} ===\n")
                f.write(patch)
                f.write("\n" + "=" * 50 + "\n")
                print(f"[+] Patch {i} appended to {PATCH_FILE}")
            else:
                print(f"[!] Skipping snippet {i}, invalid diff format")


# === AI-powered Intent classifier ===
INTENT_PROMPT = """
You are an AI intent classifier for a software engineering agent.

User will type a natural language command.
Your job: map it into one of these intents:

- static_cpp   : run static analysis on C++ project
- static_py    : run static analysis on Python project
- patch_cpp    : generate patches for C++ project
- patch_py     : generate patches for Python project
- dynamic_cpp  : run dynamic tester for C++ project
- dynamic_py   : run dynamic tester for Python project
- exit         : stop and exit the program
- unknown      : if you cannot decide

Rules:
- Output ONLY the intent label (e.g., "patch_cpp").
- Do NOT output explanations or natural text.
"""


def classify_intent(user_input: str) -> str:
    """Klasifikasi intent pakai AI (Gemini → Qwen → Ollama) dengan fallback keyword."""
    user_input_lower = user_input.lower()
    print(f"[Debug] User input: {user_input_lower}")

    # Try LLM-based classifier
    try:
        for llm, name in [(gemini_llm, "Gemini"), (qwen_llm, "Qwen"), (ollama_llm, "Ollama")]:
            if llm:
                resp = llm.invoke([HumanMessage(content=INTENT_PROMPT + f"\n\nUser: {user_input}")])
                intent = resp.content.strip().lower()
                if intent in ["static_cpp", "static_py", "patch_cpp", "patch_py", "dynamic_cpp", "dynamic_py", "exit"]:
                    print(f"[AI Intent] {intent} (via {name})")
                    return intent
    except Exception as e:
        print(f"[!] Intent LLM failed, fallback to keyword: {e}")

    # Keyword fallback
    if any(word in user_input_lower for word in ['cpp', 'c++', 'cplusplus']):
        if any(word in user_input_lower for word in ['patch', 'fix', 'repair']):
            return 'patch_cpp'
        elif any(word in user_input_lower for word in ['test', 'run', 'dynamic']):
            return 'dynamic_cpp'
        elif any(word in user_input_lower for word in ['check', 'analyze', 'static']):
            return 'static_cpp'
        else:
            return 'static_cpp'
    elif any(word in user_input_lower for word in ['py', 'python']):
        if any(word in user_input_lower for word in ['patch', 'fix', 'repair']):
            return 'patch_py'
        elif any(word in user_input_lower for word in ['test', 'run', 'dynamic']):
            return 'dynamic_py'
        elif any(word in user_input_lower for word in ['check', 'analyze', 'static']):
            return 'static_py'
        else:
            return 'static_py'
    elif any(word in user_input_lower for word in ['exit', 'quit', 'stop', 'close']):
        return 'exit'

    return "unknown"


# === Command dispatcher ===
def interpret_command(user_input: str):
    intent = classify_intent(user_input)

    if intent == "static_cpp":
        run_command("python agent/analyzer_cpp.py")
    elif intent == "static_py":
        run_command("python agent/analyzer_py.py")
    elif intent == "patch_cpp":
        run_pipeline(REPORT_CPP, SNIPPETS_CPP)
    elif intent == "patch_py":
        run_pipeline(REPORT_PY, SNIPPETS_PY)
    elif intent == "dynamic_cpp":
        run_command("python dynamic_tester.py --cpp", cwd=BASE_DIR)
    elif intent == "dynamic_py":
        run_command("python dynamic_tester.py --py", cwd=BASE_DIR)
    elif intent == "exit":
        print("Goodbye!")
        return False
    else:
        print("[!] Unknown command. Try things like:")
        print("    - 'check cpp' or 'check python'")
        print("    - 'patch cpp' or 'patch python'")
        print("    - 'test cpp' or 'test python'")
        print("    - 'exit'")
    return True


def main():
    print("AI Agent ready! What you wanna do with your code:")
    while True:
        try:
            cmd = input("\nYour command: ").strip()
            if not cmd:
                continue
            if not interpret_command(cmd):
                break
        except KeyboardInterrupt:
            print("\nProgram terminated by user")
            break
        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    main()