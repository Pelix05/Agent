import os
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import sys
import traceback
import argparse

# langchain clients are optional in developer environments; import defensively
try:
    from langchain_core.messages import HumanMessage
except Exception:
    # minimal fallback so code that constructs HumanMessage doesn't crash at import time
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content
import concurrent.futures
import multiprocessing
import time
import traceback

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:
    ChatGoogleGenerativeAI = None

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

try:
    from langchain_ollama import ChatOllama
except Exception:
    ChatOllama = None
from prompts import BUG_FIX_PROMPT

def _invoke_child_process(name, prompt, q):
    """Top-level child process target for invoking LLM clients.

    This must be at module level so it is picklable on Windows.
    """
    print(f"[DEBUG] Starting child process for {name}")
    try:
        if name == "Gemini":
            try:
                from langchain_core.messages import HumanMessage as HM
            except Exception:
                class HM:
                    def __init__(self, content: str):
                        self.content = content
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI as Client
            except Exception:
                q.put(("err", "Gemini client not installed"))
                print(f"[DEBUG] Gemini client not installed for process {name}")
                return
            key = os.getenv("GEMINI_API_KEY")
            if not key:
                q.put(("err", "GEMINI_API_KEY not set"))
                print(f"[DEBUG] GEMINI_API_KEY not set for process {name}")
                return
            client = Client(model="gemini-2.5-flash", google_api_key=key, temperature=0.1)
            resp = client.invoke([HM(content=prompt)])
            q.put(("ok", getattr(resp, "content", str(resp))))
            print(f"[DEBUG] Gemini response: {getattr(resp, 'content', str(resp))}")

        elif name == "Qwen":
            try:
                from langchain_core.messages import HumanMessage as HM
            except Exception:
                class HM:
                    def __init__(self, content: str):
                        self.content = content
            try:
                from langchain_openai import ChatOpenAI as Client
            except Exception:
                q.put(("err", "Qwen client not installed"))
                print(f"[DEBUG] Qwen client not installed for process {name}")
                return
            key = os.getenv("QWEN_API_KEY")
            if not key:
                q.put(("err", "QWEN_API_KEY not set"))
                print(f"[DEBUG] QWEN_API_KEY not set for process {name}")
                return
            client = Client(api_key=key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", model="qwen1.5-7b-chat")
            resp = client.invoke([HM(content=prompt)])
            q.put(("ok", getattr(resp, "content", str(resp))))
            print(f"[DEBUG] Qwen response: {getattr(resp, 'content', str(resp))}")

        elif name == "Ollama":
            try:
                from langchain_core.messages import HumanMessage as HM
            except Exception:
                class HM:
                    def __init__(self, content: str):
                        self.content = content
            try:
                from langchain_ollama import ChatOllama as Client
            except Exception:
                q.put(("err", "Ollama client not installed"))
                print(f"[DEBUG] Ollama client not installed for process {name}")
                return
            model = os.getenv("LOCAL_MODEL", "deepseek-coder")
            client = Client(model=model, temperature=0.3)
            resp = client.invoke([HM(content=prompt)])
            q.put(("ok", getattr(resp, "content", str(resp))))
            print(f"[DEBUG] Ollama response: {getattr(resp, 'content', str(resp))}")

        else:
            q.put(("err", f"Unknown LLM name: {name}"))
            print(f"[DEBUG] Unknown LLM name: {name} for process {name}")
    except Exception as e:
        # Attempt to put error into queue for parent to read
        try:
            print(f"[DEBUG] Child process {name} failed: {e}")
            q.put(("err", str(e)))
        except Exception:
            pass
        # Also write full traceback to a file for post-mortem debugging
        try:
            ts = int(time.time())
            pid = os.getpid()
            PATCHES_DIR = Path(__file__).resolve().parent / "patches"
            PATCHES_DIR.mkdir(exist_ok=True)
            fname = PATCHES_DIR / f"child_error_{name}_{ts}_{pid}.log"
            with open(fname, "w", encoding="utf-8") as fh:
                fh.write("Exception in child process:\n")
                traceback.print_exc(file=fh)
            print(f"[DEBUG] Traceback written to {fname}")
        except Exception:
            print(f"[DEBUG] Failed to write traceback for {name}")

# === Load env ===
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
QWEN_KEY = os.getenv("QWEN_API_KEY")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")

# If True, skip calling remote LLMs (useful for debugging/offline runs)
SKIP_LLM = False

# === LangChain Clients ===
gemini_llm = None
qwen_llm = None
ollama_llm = None

# Instantiate LLM clients only if their classes are available and keys/config present
if ChatGoogleGenerativeAI and GEMINI_KEY:
    try:
        gemini_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_KEY,
            temperature=0.1,
        )
        print(f"[DEBUG] Gemini LLM initialized with model: gemini-2.5-flash")
    except Exception as e:
        print(f"[!] Failed to init Gemini client: {e}")

if ChatOpenAI and QWEN_KEY:
    try:
        qwen_llm = ChatOpenAI(
            api_key=QWEN_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen1.5-7b-chat",
        )
        print(f"[DEBUG] Qwen LLM initialized with model: qwen1.5-7b-chat")
    except Exception as e:
        print(f"[!] Failed to init Qwen client: {e}")

if ChatOllama:
    try:
        ollama_llm = ChatOllama(model=LOCAL_MODEL, temperature=0.3)
        print(f"[DEBUG] Ollama LLM initialized with model: {LOCAL_MODEL}")
    except Exception as e:
        print(f"[!] Failed to init Ollama client: {e}")
    # Ollama client initialized (local fallback)

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
    print(f"[DEBUG] Running commands: {cmd}")
    try:
        print(f"[DEBUG] run")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        print(f"[DEBUG] Command output (stdout): {result.stdout}")
        print(f"[DEBUG] Command error (stderr): {result.stderr}")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except Exception as e:
        print(f"[!] Command execution failed: {e}", file=sys.stderr)
        print(f"[DEBUG] Exception details: {traceback.format_exc()}", file=sys.stderr)

def ask_llm(prompt: str) -> str:
    """Ask Gemini → Qwen → Ollama for a patch, with longer timeouts and graceful fallback."""
    global SKIP_LLM
    if SKIP_LLM:
        print("[Debug] SKIP_LLM is set; skipping LLM calls and returning empty patch")
        return ""

    def invoke_with_timeout(llm, name, timeout=20):
        """Invoke an LLM client in a thread with timeout."""
        if not llm:
            print(f"[Debug] {name} client not initialized, skipping.")
            return None
        print(f"[Debug] Invoking {name} (timeout={timeout}s) via thread")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(lambda: llm.invoke([HumanMessage(content=prompt)]))
                try:
                    resp = fut.result(timeout=timeout)
                    print(f"[DEBUG] {name} response received: {getattr(resp, 'content', str(resp))}")
                    return resp
                except concurrent.futures.TimeoutError:
                    print(f"[!] {name} invoke timed out after {timeout}s")
                    return None
        except Exception as e:
            print(f"[!] {name} failed during invoke: {e}")
            return None

    # Print which LLMs are available
    print(f"[Debug] LLM availability: Gemini={'yes' if gemini_llm else 'no'}, "
          f"Qwen={'yes' if qwen_llm else 'no'}, Ollama={'yes' if ollama_llm else 'no'}")

    # Try Gemini first, then Qwen, then Ollama
    for llm, name, t in [(qwen_llm, "Qwen", 60), (ollama_llm, "Ollama", 30)]:
        resp = invoke_with_timeout(llm, name, timeout=t)
        if resp is None:
            print(f"[Debug] {name} returned no response, moving to next LLM...")
            continue
        content = getattr(resp, "content", None)
        print(f"[Debug] {name} response length: {len(content) if content else 0}")
        if content and "diff --git" in content:
            print(f"[+] Patch from {name}")
            print(f"[DEBUG] Patch content: {content}")
            return content
        else:
            print(f"[Debug] {name} response did not contain a patch, skipping.")

    print("[!] All LLMs failed to produce a patch for this snippet.")
    return ""

def clean_patch_output(patch: str) -> str:
    """Clean LLM output to a valid unified diff patch."""
    print(f"[DEBUG] Cleaning patch output: {patch[:400]}...")  # Preview first 400 characters
    if not patch:
        return ""

    # Remove markdown
    patch = re.sub(r"^```diff", "", patch, flags=re.MULTILINE)
    patch = re.sub(r"^```", "", patch, flags=re.MULTILINE)

    valid_lines = []
    for line in patch.splitlines():
        line = line.rstrip()
        if line.startswith("diff --git"):
            parts = line.split()
            if len(parts) != 4:
                print(f"[DEBUG] Invalid diff --git line: {line}")
                continue
        if line.startswith(("diff --git", "--- ", "+++ ", "@@ ", "+", "-", " ")):
            # Skip empty + or - lines
            if line in ("+", "-"):
                print(f"[DEBUG] Skipping empty line: {line}")
                continue
            valid_lines.append(line)

    patch = "\n".join(valid_lines)

    if not patch.startswith("diff --git"):
        print(f"[DEBUG] Patch does not start with diff --git: {patch[:400]}...")
        return ""

    print(f"[DEBUG] Cleaned patch: {patch[:400]}...")
    return patch.strip()

def validate_patch(patch_text: str) -> bool:
    print(f"[DEBUG] Validating patch: {patch_text[:400]}...")
    if not patch_text:
        print(f"[DEBUG] Patch text is empty")
        return False
    if ("diff --git" in patch_text 
        and re.search(r"@@ -\d+,\d+ \+\d+,\d+ @@", patch_text) 
        and "--- a/" in patch_text 
        and "+++ b/" in patch_text):
        print(f"[DEBUG] Patch is valid")
        return True
    print(f"[DEBUG] Patch is invalid")
    return False

def run_pipeline(report_file, snippet_file, lang="py"):
    """
    Run patch pipeline for snippets, saving each patch separately.
    lang: "py" for Python, "cpp" for C++
    """
    print(f"[DEBUG] Running pipeline for {lang}")
    # ✅ Choose target directory based on language
    target_folder = PATCHES_DIR / f"patches_{lang}"
    target_folder.mkdir(parents=True, exist_ok=True)
    print(f"[DEBUG] Target folder: {target_folder}")

    # ✅ Basic existence check
    if not report_file.exists() or not snippet_file.exists():
        print(f"[!] Report or snippet not found.")
        print(f"[DEBUG] Report file exists: {report_file.exists()}")
        print(f"[DEBUG] Snippet file exists: {snippet_file.exists()}")
        return

    # ✅ Load report + snippets
    report = report_file.read_text(encoding="utf-8")
    snippets = snippet_file.read_text(encoding="utf-8").split("--- ")
    print(f"[DEBUG] Loaded {len(snippets) - 1} snippets from {snippet_file}")

    print(f"[*] Found {len(snippets) - 1} snippets to process in {lang.upper()} mode")

    for i, snippet in enumerate(snippets[1:], start=1):
        print(f"🔧 Processing snippet {i}...")
        print(f"[DEBUG] Snippet content: {snippet.strip()}")

        # ✅ Prepare LLM prompt
        prompt = BUG_FIX_PROMPT.format(
            code_snippet=snippet.strip(),
            analysis=report
        )
        print(f"[DEBUG] Prepared prompt: {prompt[:400]}...")  # Preview first 400 characters

        # ✅ Call LLM for patch suggestion
        raw_patch = ask_llm(prompt)
        print(f"[DEBUG] Raw patch received: {raw_patch[:400]}...")  # Preview first 400 characters

        # ✅ Save raw LLM response (for debugging)
        raw_file = target_folder / f"raw_resp_{i}.txt"
        raw_file.write_text(raw_patch or "", encoding="utf-8")
        print(f"[DEBUG] Raw response saved to {raw_file}")

        preview = (raw_patch or "").strip()[:400]
        print(f"[Debug] Raw LLM response preview (first 400 chars):\n{preview}\n--- end preview ---")

        # ✅ Clean + Sanitize Patch
        sanitized = sanitize_patch(raw_patch or "")
        patch = clean_patch_output(sanitized)
        print(f"[DEBUG] Sanitized patch: {patch[:400]}...")  # Preview first 400 characters

        # ✅ Validate before saving
        if validate_patch(patch):
            patch_file = target_folder / f"patch_{i}.diff"
            patch_file.write_text(patch, encoding="utf-8")
            print(f"[+] ✅ Patch {i} written to {patch_file}")
        else:
            print(f"[!] ⚠️ Skipping snippet {i}, invalid diff format")
            skipped_file = target_folder / f"skipped_patch_{i}.txt"
            skipped_file.write_text(raw_patch or "", encoding="utf-8")
            print(f"[DEBUG] Skipped patch saved to {skipped_file}")

def sanitize_patch(raw_patch: str) -> str:
    """
    Remove markdown code blocks, explanations, and any text after the diff body.
    Ensures only valid unified diff remains.
    """
    print(f"[DEBUG] Sanitizing patch: {raw_patch[:400]}...")  # Preview first 400 characters
    lines = raw_patch.strip().splitlines()
    clean_lines = []
    inside_patch = False

    for line in lines:
        # Start when we see the diff header
        if line.startswith("diff --git"):
            inside_patch = True
            clean_lines = [line]
            print(f"[DEBUG] Started patch with diff header: {line}")
            continue
        if not inside_patch:
            continue

        # Stop when explanation or markdown starts
        if line.strip().startswith("Explanation:") or line.strip().startswith("```"):
            print(f"[DEBUG] Stopped patch at line: {line}")
            break

        # Accept only valid diff lines
        if line.startswith(("index ", "--- ", "+++ ", "@@ ", "+", "-", " ")):
            if line in ("+", "-"):
                print(f"[DEBUG] Skipping empty line: {line}")
                continue
            clean_lines.append(line)

    sanitized_patch = "\n".join(clean_lines).strip()
    print(f"[DEBUG] Sanitized patch: {sanitized_patch[:400]}...")  # Preview first 400 characters
    return sanitized_patch

def count_static_issues(report_path: Path) -> int:
    """Count linter-style issues in the static analysis report file.

    We look for lines that match the pylint/flake8 style: path:line:col: CODE: message
    """
    print(f"[DEBUG] Counting static issues in {report_path}")
    import re as _re
    if not report_path.exists():
        print(f"[DEBUG] Report file {report_path} does not exist")
        return -1
    text = report_path.read_text(encoding="utf-8")
    # Match patterns like "file.py:12:8: E1101: ..." or "file.py:12: E0606: ..."
    matches = _re.findall(r"^.+?:\d+:\d+:\s+[A-Z]\d{4}:", text, flags=_re.MULTILINE)
    print(f"[DEBUG] Found {len(matches)} matches with col: {matches[:10]}...")  # Preview first 10 matches
    if not matches:
        # fallback: some tools may emit file:line:code style without column
        matches = _re.findall(r"^.+?:\d+:\s+[A-Z]\d{4}:", text, flags=_re.MULTILINE)
        print(f"[DEBUG] Found {len(matches)} matches without col: {matches[:10]}...")  # Preview first 10 matches
    print(f"[DEBUG] Total static issues found: {len(matches)}")
    return len(matches)

def run_iterative_fix_py(max_iters: int = 5):
    """Run an iterative loop: static analysis -> generate patches -> apply via dynamic tests -> repeat.

    Stops when static issue count reaches 0 or when issues don't decrease between iterations.
    """
    print("[*] Starting iterative auto-fix loop for Python")
    prev_issues = None
    for iteration in range(1, max_iters + 1):
        print(f"\n=== Iteration {iteration}/{max_iters} ===")
        print(f"[DEBUG] Starting iteration {iteration}")

        # 1) Run static analyzer (use py -3 to pick correct interpreter)
        print("[*] Running static analyzer (py)")
        run_command("py -3 -u agent/analyzer_py.py", cwd=BASE_DIR)

        issues = count_static_issues(REPORT_PY)
        print(f"[*] Static issues found: {issues}")
        print(f"[DEBUG] Static issues count: {issues}")

        if issues == 0:
            print("[+] No static issues remain. Auto-fix complete.")
            return True

        if prev_issues is not None and issues >= prev_issues:
            print("[!] Static issue count did not decrease this iteration. Aborting to avoid loop.")
            return False

        prev_issues = issues

        # 2) Generate candidate patches for Python snippets
        print("[*] Generating candidate patches (LLM)")
        run_pipeline(REPORT_PY, SNIPPETS_PY, lang="py")

        # 3) Run dynamic tester which will attempt to apply patches and run runtime tests
        print("[*] Running dynamic tester to apply patches and test runtime behavior")
        run_command("py -3 -u agent/dynamic_tester.py --py", cwd=BASE_DIR)

        # 4) Re-run static analyzer next loop to measure improvement
    print("[!] Reached max iterations without fully resolving static issues.")
    return False

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

    # Keyword fallback first (avoid blocking on unavailable LLMs)
    if any(word in user_input_lower for word in ['cpp', 'c++', 'cplusplus']):
        if any(word in user_input_lower for word in ['patch', 'fix', 'repair']):
            print(f"[DEBUG] Classifying intent: patch_cpp")
            return 'patch_cpp'
        elif any(word in user_input_lower for word in ['test', 'run', 'dynamic']):
            print(f"[DEBUG] Classifying intent: dynamic_cpp")
            return 'dynamic_cpp'
        elif any(word in user_input_lower for word in ['check', 'analyze', 'static']):
            print(f"[DEBUG] Classifying intent: static_cpp")
            return 'static_cpp'
        else:
            print(f"[DEBUG] Classifying intent: static_cpp (default)")
            return 'static_cpp'
    elif any(word in user_input_lower for word in ['py', 'python']):
        if any(word in user_input_lower for word in ['patch', 'fix', 'repair']):
            print(f"[DEBUG] Classifying intent: patch_py")
            return 'patch_py'
        elif any(word in user_input_lower for word in ['test', 'run', 'dynamic']):
            print(f"[DEBUG] Classifying intent: dynamic_py")
            return 'dynamic_py'
        elif any(word in user_input_lower for word in ['check', 'analyze', 'static']):
            print(f"[DEBUG] Classifying intent: static_py")
            return 'static_py'
        else:
            print(f"[DEBUG] Classifying intent: static_py (default)")
            return 'static_py'
    elif any(word in user_input_lower for word in ['exit', 'quit', 'stop', 'close']):
        print(f"[DEBUG] Classifying intent: exit")
        return 'exit'
    # If keywords couldn't decide, try the LLMs as a last resort
    try:
        for llm, name in [(gemini_llm, "Gemini"), (qwen_llm, "Qwen"), (ollama_llm, "Ollama")]:
            if llm:
                resp = llm.invoke([HumanMessage(content=INTENT_PROMPT + f"\n\nUser: {user_input}")])
                intent = getattr(resp, 'content', str(resp)).strip().lower()
                print(f"[AI Intent] {intent} (via {name})")
                print(f"[DEBUG] Intent received from {name}: {intent}")
                if intent in ["static_cpp", "static_py", "patch_cpp", "patch_py", "dynamic_cpp", "dynamic_py", "exit"]:
                    return intent
    except Exception as e:
        print(f"[!] Intent LLM failed (final fallback): {e}")

    print(f"[DEBUG] Classifying intent: unknown")
    return "unknown"

# === Command dispatcher ===
def interpret_command(user_input: str):
    intent = classify_intent(user_input)
    print(f"[DEBUG] Interpreted intent: {intent}")

    if intent == "static_cpp":
        run_command("python agent/analyzer_cpp.py")
    elif intent == "static_py":
        run_command("python agent/analyzer_py.py")
    elif intent == "patch_cpp":
        run_pipeline(REPORT_CPP, SNIPPETS_CPP, lang="cpp")
    elif intent == "patch_py":
        run_pipeline(REPORT_PY, SNIPPETS_PY, lang="py")
    elif intent == "dynamic_cpp":
        run_command(f'python -u dynamic_tester.py --cpp', cwd=BASE_DIR)
    elif intent == "dynamic_py":
        run_command("python dynamic_tester.py --py", cwd=BASE_DIR)
    elif user_input.strip().lower() == "auto_fix_py":
        # Special non-LLM keyword to run the iterative auto-fix loop for Python
        run_iterative_fix_py(max_iters=5)
    elif intent == "exit":
        print("Goodbye!")
        print(f"[DEBUG] Exiting program")
        return False
    else:
        print("[!] Unknown command. Try things like:")
        print("    - 'check cpp' or 'check python'")
        print("    - 'patch cpp' or 'patch python'")
        print("    - 'test cpp' or 'test python'")
        print("    - 'exit'")
    print(f"[DEBUG] Command interpretation completed for: {user_input}")
    return True

def main():
    print("AI Agent ready! What you wanna do with your code:")
    while True:
        try:
            cmd = input("\nYour command: ").strip()
            print(f"[DEBUG] Received command: {cmd}")
            if not cmd:
                continue
            if not interpret_command(cmd):
                break
        except KeyboardInterrupt:
            print("\nProgram terminated by user")
            print(f"[DEBUG] Program terminated by user")
            break
        except Exception as e:
            print(f"[!] Error: {e}")
            print(f"[DEBUG] Error details: {traceback.format_exc()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent runner")
    parser.add_argument("--cmd", type=str, help="Run single command and exit (e.g. --cmd \"patch cpp\")")
    parser.add_argument("--no-llm", action="store_true", help="Skip remote LLM calls (debug/offline)")
    args = parser.parse_args()

    if args.no_llm:
        SKIP_LLM = True
        print(f"[DEBUG] SKIP_LLM set to: {SKIP_LLM}")

    if args.cmd:
        print(f"[DEBUG] Running single command: {args.cmd}")
        # Run a single command non-interactively and exit
        if args.cmd.strip().lower() == "auto_fix_py":
            run_iterative_fix_py(max_iters=10)
        else:
            interpret_command(args.cmd)
    else:
        print(f"[DEBUG] Entering interactive mode")
        main()
