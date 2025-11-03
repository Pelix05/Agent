from flask import Flask, request, jsonify, render_template
import subprocess
import os
import tempfile
from pathlib import Path
import zipfile
import difflib
from lc_pipeline import run_iterative_fix_py, run_pipeline, REPORT_PY, SNIPPETS_PY

app = Flask(__name__)

# Global state
file_uploaded = False
uploaded_python_files = []
uploaded_cpp_files = []

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


def run_static_analysis_py():
    """Run static analysis for Python (e.g., pylint, bandit)."""
    return run_command("python analyzer_py.py", cwd="agent")


def run_dynamic_py():
    """Run dynamic tests for Python."""
    return run_command("python dynamic_tester.py --py", cwd="agent")


def run_static_analysis_cpp():
    """Run static analysis for C++ (e.g., cppcheck, clang-tidy)."""
    return run_command("cppcheck --enable=all .", cwd="cpp_project")


def run_dynamic_cpp():
    """Run dynamic tests for C++."""
    return run_command("python dynamic_tester.py --cpp", cwd="agent")


def run_patch_py():
    """Run patch pipeline for Python."""
    original_file = uploaded_python_files[0]  # Assuming single file for simplicity
    patched_file = f"{original_file.stem}_patched.py"  # The patched file's name

    # Apply the patch (this can be customized based on your logic)
    patch_result = run_pipeline(REPORT_PY, SNIPPETS_PY, lang="py")

    # Save the patched file (you can modify this part as per your actual logic)
    with open(patched_file, 'w') as patched:
        patched.write(patch_result)

    return f"Patch applied! You can now compare the files: {original_file.name} vs {patched_file}"


def run_auto_fix_py():
    """Run iterative auto-fix loop for Python."""
    return run_iterative_fix_py(max_iters=5)


def compare_files(original_file, patched_file):
    """Compare the original and patched files to prove the patch was applied."""
    with open(original_file, 'r') as f1, open(patched_file, 'r') as f2:
        original_code = f1.readlines()
        patched_code = f2.readlines()

    diff = difflib.unified_diff(original_code, patched_code, fromfile='original_code.py', tofile='patched_code.py')

    return '\n'.join(diff)  # Return the diff as a string


# === File Upload Handler ===

def handle_file_upload(file, file_type="py"):
    """Handle ZIP file upload, extract, and run both static and dynamic analysis."""
    global file_uploaded, uploaded_python_files, uploaded_cpp_files
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

            # Find Python or C++ files based on the file type
            if file_type == "py":
                python_files = [f for f in Path(tmpdir).rglob("*.py")]
                cpp_files = [f for f in Path(tmpdir).rglob("*.cpp")]
                header_files = [f for f in Path(tmpdir).rglob("*.h")]

                if not python_files and not cpp_files:
                    return "No Python or C++ files found in the uploaded zip."

                file_uploaded = True
                uploaded_python_files = python_files if python_files else cpp_files


                # Run Static Analysis
                static_results = ["=== STATIC ANALYSIS ==="]
                for py_file in python_files:
                    static_results.append(f"\n--- Static Analysis for {py_file.name} ---\n")
                    static_results.append(run_static_analysis_py())

                # Run Dynamic Analysis
                dynamic_results = ["\n=== DYNAMIC ANALYSIS ===\n"]
                dynamic_results.append(run_dynamic_py())

                return "\n".join(static_results + dynamic_results)

            elif file_type == "cpp":
                cpp_files = [f for f in Path(tmpdir).rglob("*.cpp")]
                if not cpp_files:
                    return "No C++ files found in the uploaded zip."
                file_uploaded = True
                uploaded_cpp_files = cpp_files

                # Run Static Analysis for C++
                static_results = ["=== STATIC ANALYSIS ==="]
                for cpp_file in cpp_files:
                    static_results.append(f"\n--- Static Analysis for {cpp_file.name} ---\n")
                    static_results.append(run_static_analysis_cpp())

                # Run Dynamic Analysis for C++
                dynamic_results = ["\n=== DYNAMIC ANALYSIS ===\n"]
                dynamic_results.append(run_dynamic_cpp())

                return "\n".join(static_results + dynamic_results)

    except Exception as e:
        return f"[Error] Upload failed: {str(e)}"


# === Command Interpreter ===

def interpret_command(user_input: str):
    """Interpret user command and execute corresponding function."""
    user_input_lower = user_input.strip().lower()

    try:
        # Conversation responses
        if "hello" in user_input_lower or "hi" in user_input_lower:
            return "Hello! 👋 Ready to analyze your code."
        elif "how are you" in user_input_lower:
            return "I'm great! Let's fix some code today 😄"
        elif "bye" in user_input_lower:
            return "Goodbye! 👋"

        # Require upload first
        if not file_uploaded:
            return "⚠️ Please upload a file before running commands."

        # Command matching
        if "static" in user_input_lower and "py" in user_input_lower:
            return run_static_analysis_py()
        elif "dynamic" in user_input_lower and "py" in user_input_lower:
            return run_dynamic_py()
        elif "static" in user_input_lower and "cpp" in user_input_lower:
            return run_static_analysis_cpp()
        elif "dynamic" in user_input_lower and "cpp" in user_input_lower:
            return run_dynamic_cpp()
        elif "patch" in user_input_lower and "py" in user_input_lower:
            return run_patch_py()
        elif "auto_fix" in user_input_lower and "py" in user_input_lower:
            return run_auto_fix_py()
        elif "compare" in user_input_lower and "patch" in user_input_lower:
            return compare_patch()
        else:
            return "❓ Unknown command. Try: static py | dynamic py | patch py | auto_fix py | compare patch | static cpp | dynamic cpp"
    except Exception as e:
        return f"[Error] {str(e)}"


# === Flask Routes ===

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file_route():
    """Handle ZIP file upload."""
    if 'file' not in request.files:
        return jsonify({"status": "Error", "error": "No file part"})
    file = request.files['file']
    file_type = request.form.get('file_type', 'py')  # Default to 'py', can be overridden via form

    if file.filename == '':
        return jsonify({"status": "Error", "error": "No selected file"})

    result = handle_file_upload(file, file_type)
    return jsonify({"status": "Success", "result": result})


@app.route('/process', methods=['POST'])
def process_command():
    """Handle text commands."""
    user_input = request.form.get('command')
    if not user_input:
        return jsonify({"status": "Error", "error": "No command entered."})

    result = interpret_command(user_input)

    # Check for patch-related commands
    if "patch py" in user_input.lower():
        # Ensure the file has been uploaded first
        if not file_uploaded:
            return jsonify({"status": "Error", "error": "No file uploaded."})

        patch_result = run_patch_py()
        return jsonify({"status": "Success", "result": patch_result})

    # If it's an auto-fix command
    if "auto_fix py" in user_input.lower():
        # Run the auto-fix process and show progress
        auto_fix_result = run_auto_fix_py()
        return jsonify({"status": "Success", "result": auto_fix_result})

    return jsonify({"status": "Success", "result": result})


@app.route('/compare_patch', methods=['POST'])
def compare_patch():
    """Compare original file and patched file."""
    if not file_uploaded:
        return jsonify({"status": "Error", "error": "No file uploaded for patch comparison."})

    original_file = uploaded_python_files[0] if uploaded_python_files else uploaded_cpp_files[0]
    patched_file = f"{original_file.stem}_patched.py" if uploaded_python_files else f"{original_file.stem}_patched.cpp"

    if not os.path.exists(patched_file):
        return jsonify({"status": "Error", "error": "Patched file not found."})

    # Get the diff between the original and patched files
    diff = compare_files(original_file, patched_file)
    
    return jsonify({"status": "Success", "diff": diff})


# === Config ===

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['STATIC_FOLDER'] = 'static'
app.config['TEMPLATES_FOLDER'] = 'templates'


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
