import os
import re
import sys
import ast
import shutil
import difflib
import subprocess
import argparse
from groq import Groq

SYSTEM_PROMPT = """You are an autonomous senior software engineering agent.
Your goal is to inspect a project codebase, analyze a requested task or bug fix, and make coordinated edits across necessary files.

OUTPUT FORMAT INSTRUCTIONS:
You MUST return your proposed file modifications using EXACTLY this file block structure for EACH file modified:

<<<FILE: relative/path/to/filename.py>>>
[Full updated code for the file]
<<<END_FILE>>>

CRITICAL RULES:
1. Do NOT wrap <<<FILE: ...>>> blocks inside markdown code fences (```python ... ```).
2. Always output the FULL updated code for each file, never partial snippets or placeholders.
3. Keep logic clean, correct, and self-contained.
"""

def get_active_model(client: Groq) -> str:
    """Dynamically selects an active text model while filtering out security/audio models."""
    try:
        available_models = [m.id for m in client.models.list().data]
        ignored_keywords = ["guard", "whisper", "vision", "embed", "safeguard"]
        valid_models = [
            m for m in available_models 
            if not any(k in m.lower() for k in ignored_keywords)
        ]
        for m in valid_models:
            if any(name in m.lower() for name in ["llama-3.3", "llama-3.1", "qwen", "mixtral", "gemma"]):
                return m
        return valid_models[0] if valid_models else "llama-3.3-70b-versatile"
    except Exception:
        return "llama-3.3-70b-versatile"

def summarize_repository(project_dir: str) -> dict:
    """
    Scans Python files in project_dir, extracts AST function/class signatures,
    and returns file contents mapped by relative paths.
    """
    summary = {}
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file.endswith(".py") and not file.endswith(".bak"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, project_dir)
                
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    continue
                
                signatures = []
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            args = [arg.arg for arg in node.args.args]
                            signatures.append(f"  - def {node.name}({', '.join(args)})")
                        elif isinstance(node, ast.ClassDef):
                            signatures.append(f"  - class {node.name}")
                except Exception:
                    signatures.append("  - (AST parsing failed)")
                
                summary[rel_path] = {
                    "content": content,
                    "signatures": "\n".join(signatures)
                }
    return summary

def generate_unified_diff(original_code: str, new_code: str, filename: str) -> str:
    """Generates a git-style unified diff string."""
    orig_lines = original_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    )
    return "".join(diff)

def parse_proposed_edits(response_text: str) -> list[tuple[str, str]]:
    """Extracts (relative_filename, new_code) tuples from model output."""
    pattern = r"<<<FILE:\s*(.*?)>>>\s*\n(.*?)\s*<<<END_FILE>>>"
    matches = re.findall(pattern, response_text, re.DOTALL)
    edits = []
    for filename, new_code in matches:
        filename = filename.strip()
        clean_code = re.sub(r"^```(?:python)?\s*\n?", "", new_code.strip(), flags=re.IGNORECASE)
        clean_code = re.sub(r"\n?\s*```$", "", clean_code).strip()
        edits.append((filename, clean_code))
    return edits

def apply_edits_to_disk(project_dir: str, edits: list[tuple[str, str]]):
    """Backs up existing files (.bak) and applies new edits to disk."""
    for rel_path, new_code in edits:
        full_path = os.path.join(project_dir, rel_path)
        
        # Backup if file already exists
        if os.path.exists(full_path):
            backup_path = full_path + ".bak"
            shutil.copyfile(full_path, backup_path)
            print(f" [Backup Created] {rel_path} -> {rel_path}.bak")
        
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_code + "\n")
        print(f" [File Updated] {rel_path}")

def run_project_tests(project_dir: str, test_cmd: str, timeout: int = 10) -> tuple[bool, str]:
    """Runs test suite inside isolated subprocess with safety timeout."""
    print(f"\n [Executing Tests] CMD: '{test_cmd}' (Timeout: {timeout}s)...")
    try:
        # Split command string into list for subprocess execution
        cmd_args = test_cmd.split()
        # If running unittest, default to system Python executable
        if cmd_args[0].lower() in ["python", "python3"]:
            cmd_args[0] = sys.executable

        result = subprocess.run(
            cmd_args,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        combined_output = (result.stdout + "\n" + result.stderr).strip()
        passed = (result.returncode == 0)
        return passed, combined_output
    except subprocess.TimeoutExpired:
        return False, f"TimeoutError: Test execution exceeded safety limit of {timeout} seconds."
    except Exception as e:
        return False, f"Subprocess Error: {str(e)}"

def run_agent(project_dir: str, task: str, test_cmd: str, dry_run: bool = False, max_attempts: int = 3, timeout: int = 10):
    api_key = os.environ.get("GROQ_API_KEY") or "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"
    client = Groq(api_key=api_key)
    model_name = get_active_model(client)

    print("=" * 70)
    print(" SKILLAUDIT AI: AUTONOMOUS CODING AGENT")
    print("=" * 70)
    print(f" Target Project : {os.path.abspath(project_dir)}")
    print(f" Task Prompt    : {task}")
    print(f" Test Command   : {test_cmd}")
    print(f" Active Model   : {model_name}")
    print(f" Dry Run Mode   : {dry_run}")
    print("=" * 70)

    # 1. SCAN AND SUMMARIZE REPOSITORY
    repo_summary = summarize_repository(project_dir)
    if not repo_summary:
        print(f"Error: No Python files found in directory '{project_dir}'.")
        return False

    context_prompt = "REPOSITORY STRUCTURE & FILE CONTENTS:\n\n"
    for rel_path, data in repo_summary.items():
        context_prompt += f"=== FILE: {rel_path} ===\n"
        context_prompt += f"Signatures:\n{data['signatures']}\n\n"
        context_prompt += f"Content:\n{data['content']}\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context_prompt}\nUSER TASK:\n{task}"}
    ]

    for attempt in range(1, max_attempts + 1):
        print(f"\n" + "-" * 70)
        print(f" EXECUTION ATTEMPT {attempt}/{max_attempts}")
        print("-" * 70)

        # GENERATE FIX
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1
        )
        response_text = response.choices[0].message.content
        edits = parse_proposed_edits(response_text)

        if not edits:
            print(" Warning: Agent did not output file modification delimiters.")
            print("Raw Response:\n", response_text)

        # SHOW PROPOSED DIFFS
        print("\n PROPOSED UNIFIED DIFFS:")
        print("=" * 40)
        for rel_path, new_code in edits:
            orig_code = repo_summary.get(rel_path, {}).get("content", "")
            diff = generate_unified_diff(orig_code, new_code, rel_path)
            if diff:
                print(diff)
            else:
                print(f" No line changes detected for {rel_path}.")
        print("=" * 40)

        # HANDLE --dry-run
        if dry_run:
            print("\n [DRY-RUN MODE] Diffs previewed. No files modified. Exiting.")
            return True

        # APPLY EDITS TO DISK
        apply_edits_to_disk(project_dir, edits)

        # EXECUTE TESTS & OBSERVE
        passed, test_output = run_project_tests(project_dir, test_cmd, timeout=timeout)

        if passed:
            print(f"\n SUCCESS! ALL TESTS PASSED ON ATTEMPT {attempt}.")
            print(f"Test Execution Output:\n{test_output}")
            return True
        else:
            print(f"\n TEST EXECUTION FAILED!")
            print(f"Traceback / Error Output:\n{test_output}")

            if attempt < max_attempts:
                print(f"\n Feeding test error back to LLM for Attempt {attempt + 1}...")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The proposed edits failed the test suite with the following error output:\n\n"
                        f"{test_output}\n\n"
                        f"Please analyze the failure, correct the code, and return updated <<<FILE: ...>>> blocks."
                    )
                })

    print(f"\n AGENT FAILED to resolve task after {max_attempts} attempts.")
    return False

def main():
    parser = argparse.ArgumentParser(description="SkillAudit Portfolio Coding-Agent CLI")
    parser.add_argument("--project", type=str, required=True, help="Path to target project directory")
    parser.add_argument("--task", type=str, required=True, help="Natural language bug fix or feature task")
    parser.add_argument("--test-cmd", type=str, default="python -m unittest test_calculator.py", help="Command to run project test suite")
    parser.add_argument("--dry-run", action="store_true", help="Preview proposed diffs without applying edits to disk")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum self-correction attempts")
    parser.add_argument("--timeout", type=int, default=10, help="Subprocess timeout limit in seconds")

    args = parser.parse_args()

    run_agent(
        project_dir=args.project,
        task=args.task,
        test_cmd=args.test_cmd,
        dry_run=args.dry_run,
        max_attempts=args.max_attempts,
        timeout=args.timeout
    )

if __name__ == "__main__":
    main()