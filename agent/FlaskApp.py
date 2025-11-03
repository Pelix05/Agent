from flask import Flask, request, jsonify, render_template
import subprocess
import os
from pathlib import Path
import zipfile
import tempfile
from lc_pipeline import run_iterative_fix_py, run_pipeline, REPORT_PY, SNIPPETS_PY  # your pipeline imports

app = Flask(__name__)

# Global state
file_uploaded = False
uploaded_files = []
current_stage = 0
stages = ["static_analysis", "dynamic_analysis", "patch", "auto_fix"]

# === Helper Functions ===

def run_command(cmd, cwd=None):
    """Run a shell command and capture the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        return result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        return f"[Error] {e.stdout}\n{e.stderr}"
    except Exception as e:
        return f"[Error] {str(e)}"

def run_static_analysis_py(tmpdir):
    """Run static analysis (example: pylint, bandit) for Python files."""
    python_files = [f for f in Path(tmpdir).rglob("*.py")]
    results = []
    for py_file in python_files:
        result = run_command(f"python analyzer_py.py {py_file}", cwd="agent")
        results.append(f"--- Static Analysis for {py_file.name} ---\n{result}")
    return "\n".join(results)

def run_static_analysis_cpp(tmpdir):
    """Run static analysis (example: cppcheck) for C++ files."""
    cpp_files = [f for f in Path(tmpdir).rglob("*.cpp")]
    results = []
    for cpp_file in cpp_files:
        result = run_command(f"cppcheck {cpp_file}", cwd="agent")
        results.append(f"--- Static Analysis for {cpp_file.name} ---\n{result}")
    return "\n".join(results)

def run_dynamic_analysis_py(tmpdir):
    """Run dynamic tests for Python."""
    return run_command("python dynamic_tester.py --py", cwd="agent")

def run_dynamic_analysis_cpp(tmpdir):
    """Run dynamic tests for C++."""
    return run_command("cpp_tester --cpp", cwd="agent")

def run_patch_py():
    """Run patch pipeline for Python."""
    return run_pipeline(REPORT_PY, SNIPPETS_PY, lang="py")

def run_patch_cpp():
    """Run patch pipeline for C++."""
    return run_pipeline(REPORT_CPP, SNIPPETS_CPP, lang="cpp")

def run_auto_fix_py():
    """Run iterative auto-fix loop for Python."""
    return run_iterative_fix_py(max_iters=5)

def run_auto_fix_cpp():
    """Run iterative auto-fix loop for C++."""
    return run_iterative_fix_py(max_iters=5)

# === File Upload Handler ===

def handle_file_upload(file):
    """Handle ZIP file upload, extract, and prepare for analysis."""
    global file_uploaded, uploaded_files
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, file.filename)
            file.save(file_path)

            # Extract ZIP
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
            else:
                return "[Error] The uploaded file is not a valid ZIP file."

            # Find Python and C++ files
            python_files = [f for f in Path(tmpdir).rglob("*.py")]
            cpp_files = [f for f in Path(tmpdir).rglob("*.cpp")]
            if not python_files and not cpp_files:
                return "No Python or C++ files found in the uploaded zip."

            file_uploaded = True
            uploaded_files = {"py": python_files, "cpp": cpp_files}

            return tmpdir

    except Exception as e:
        return f"[Error] Upload failed: {str(e)}"

# === Automation Controller ===

def run_next_stage(tmpdir):
    """Run the next stage in the automation pipeline."""
    global current_stage, stages
    if current_stage >= len(stages):
        return "All stages completed."

    if stages[current_stage] == "static_analysis":
        result_py = run_static_analysis_py(tmpdir) if uploaded_files["py"] else "No Python files found."
        result_cpp = run_static_analysis_cpp(tmpdir) if uploaded_files["cpp"] else "No C++ files found."
        return f"=== STATIC ANALYSIS ===\n{result_py}\n{result_cpp}"
    elif stages[current_stage] == "dynamic_analysis":
        result_py = run_dynamic_analysis_py(tmpdir) if uploaded_files["py"] else "No Python files found."
        result_cpp = run_dynamic_analysis_cpp(tmpdir) if uploaded_files["cpp"] else "No C++ files found."
        return f"=== DYNAMIC ANALYSIS ===\n{result_py}\n{result_cpp}"
    elif stages[current_stage] == "patch":
        result_py = run_patch_py() if uploaded_files["py"] else "No Python files found."
        result_cpp = run_patch_cpp() if uploaded_files["cpp"] else "No C++ files found."
        return f"=== PATCH ===\n{result_py}\n{result_cpp}"
    elif stages[current_stage] == "auto_fix":
        result_py = run_auto_fix_py() if uploaded_files["py"] else "No Python files found."
        result_cpp = run_auto_fix_cpp() if uploaded_files["cpp"] else "No C++ files found."
        return f"=== AUTO FIX ===\n{result_py}\n{result_cpp}"

# === Command Interpreter ===

def interpret_command(user_input: str):
    """Interpret user command and execute corresponding function."""
    user_input_lower = user_input.strip().lower()

    try:
        # Conversation responses
        if "hello" in user_input_lower or "hi" in user_input_lower:
            return "Hello! 👋 Ready to analyze your files."
        elif "how are you" in user_input_lower:
            return "I'm great! Let's fix some code today 😄"
        elif "bye" in user_input_lower:
            return "Goodbye! 👋"

        # Require upload first
        if not file_uploaded:
            return "⚠️ Please upload a file before running commands."

        # Command matching
        if "next" in user_input_lower:
            global current_stage
            current_stage += 1
            result = run_next_stage(tmpdir)
            return result
        else:
            return "❓ Unknown command. Try: next"
    except Exception as e:
        return f"[Error] {str(e)}"

# === Flask Routes ===

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle ZIP file upload."""
    if 'file' not in request.files:
        return jsonify({"status": "Error", "error": "No file part"})
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "Error", "error": "No selected file"})

    global tmpdir
    tmpdir = handle_file_upload(file)

    if isinstance(tmpdir, str) and tmpdir.startswith("[Error]"):
        return jsonify({"status": "Error", "error": tmpdir})

    return jsonify({"status": "Success", "result": "File uploaded successfully. Ready to start analysis."})

@app.route('/process', methods=['POST'])
def process_command():
    """Handle text commands."""
    user_input = request.form.get('command')
    if not user_input:
        return jsonify({"status": "Error", "error": "No command entered."})

    result = interpret_command(user_input)
    return jsonify({"status": "Success", "result": result})

# === Config ===

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['STATIC_FOLDER'] = 'static'
app.config['TEMPLATES_FOLDER'] = 'templates'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
