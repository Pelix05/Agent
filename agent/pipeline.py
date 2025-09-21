import os
from pathlib import Path
try:
    import requests
except Exception:
    requests = None

try:
    from dotenv import load_dotenv
except Exception:
    # provide a no-op fallback so tests which import this module don't fail
    def load_dotenv(*args, **kwargs):
        return None
try:
    import google.generativeai as genai
except Exception:
    genai = None
from prompts import BUG_FIX_PROMPT  
try:
    import ollama
except Exception:
    ollama = None
from typing import Optional
try:
    # prefer local parser if present in workspace (agent/patch_parser.py)
    from patch_parser import validate_unified_diff, parse_changed_files_from_report, PatchValidationError
except Exception:
    # fallback to helper in this module if not importable
    validate_unified_diff = None
    parse_changed_files_from_report = None
    PatchValidationError = Exception

# === Load env ===
load_dotenv()

# Gemini setup
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Local Ollama setup
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "codellama")

# === Folder setup ===
BASE_DIR = Path(__file__).resolve().parent
SNIPPETS_DIR = BASE_DIR / "snippets"
PATCHES_DIR = BASE_DIR / "patches"
PATCHES_DIR.mkdir(exist_ok=True)

REPORT_FILE = BASE_DIR / "analysis_report_cpp.txt"
SNIPPET_FILE = SNIPPETS_DIR / "bug_snippets_cpp.txt"
PATCH_FILE = PATCHES_DIR / "all_patches.md"

def ask_llm(prompt: str) -> str:
    """Try Gemini first, fallback ke local Ollama."""
    # Priority 1: Gemini
    if GEMINI_KEY:
        try:
            model = genai.GenerativeModel("models/gemma-3-1b-it")
            resp = model.generate_content(prompt)
            return resp.text
        except Exception as e:
            print(f"[!] Gemini failed ({e}) → fallback ke local model...")

    # Priority 2: Ollama (if available)
    if ollama is not None:
        try:
            response = ollama.chat(
                model=LOCAL_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                options={
                    'temperature': 0.3,
                    'num_predict': 600,
                    'top_k': 40,
                    'top_p': 0.8
                }
            )
            return response['message']['content']
        except Exception as e:
            print(f"[!] Ollama failed ({e}) → fallback ke HTTP API...")
        
        # Priority 3: Fallback ke HTTP API
        try:
            payload = {
                "model": LOCAL_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            
            r = requests.post("http://localhost:11434/api/chat", json=payload, timeout=60)
            response_data = r.json()
            
            # Handle Ollama response format
            if 'message' in response_data and 'content' in response_data['message']:
                return response_data['message']['content']
            else:
                print(f"Unexpected response format: {response_data}")
                return "Error: Unexpected response format"
                
        except Exception as http_error:
            print(f"[!] HTTP API also failed ({http_error})")
            
            # Final fallback: simple response
            return "AI service unavailable. Please check Ollama installation."

def run_pipeline():
    if not REPORT_FILE.exists() or not SNIPPET_FILE.exists():
        print("[!] Report atau snippet tidak ditemukan. Jalankan analyzer dulu.")
        return

    # Check ollama availability
    try:
        models = ollama.list()
        print("✅ Ollama models available:")
        for model in models['models']:
            print(f"  - {model['name']}")
    except Exception as e:
        print(f"⚠️  Ollama warning: {e}")
        print("Continuing with fallbacks...")

    report = REPORT_FILE.read_text(encoding="utf-8")
    snippets = SNIPPET_FILE.read_text(encoding="utf-8").split("--- ")

    print(f"[*] Found {len(snippets)-1} snippets to process")

    # Prepare allowed files set from report for parser checks (if parser available)
    allowed_files = set()
    if parse_changed_files_from_report is not None:
        allowed_files = parse_changed_files_from_report(report)

    with open(PATCH_FILE, "w", encoding="utf-8") as f:
        for i, snippet in enumerate(snippets[1:], start=1):
            print(f"🔧 Processing snippet {i}...")
            prompt = BUG_FIX_PROMPT.format(
                bug_report=report,
                code_snippet=snippet.strip()
            )

            patch = ask_llm(prompt)

            # Validate patch if possible
            valid = True
            if validate_unified_diff is not None:
                try:
                    validate_unified_diff(patch, allowed_files)
                except PatchValidationError as e:
                    print(f"[!] Patch {i} rejected by parser: {e}")
                    valid = False

            if not patch or not valid:
                f.write(f"\n\n=== PATCH {i} ===\n")
                f.write("ERROR: Invalid or empty patch. Skipped.\n")
                continue

            f.write(f"\n\n=== PATCH {i} ===\n")
            f.write(patch.strip())
            f.write("\n" + "="*50 + "\n")

            print(f"[+] Patch {i} appended to {PATCH_FILE}")

if __name__ == "__main__":
    run_pipeline()