import os
import re
import sys
import ast
import shutil
import subprocess
import argparse
from groq import Groq

SYSTEM_PROMPT = """You are an expert multi-file Python coding agent.
Your task is to analyze a project's context, understand user instructions, and edit or create files to fulfill the request.

OUTPUT FORMAT INSTRUCTIONS:
To update or create files, format your response using EXACTLY this file delimiter structure for EACH file you need to modify:

<<<FILE: filename.py>>>
[Full updated code for filename.py]
<<<END_FILE>>>

Do NOT put markdown code fences (```) around the file delimiter blocks. Include FULL file contents, not snippets.
"""

def get_active_model(client: Groq) -> str:
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

def summarize_project(project_dir: str) -> dict:
    summary = {}
    for root, _, files in os.walk(project_dir):
        for file in files:
            if file.endswith(".py") and not file.endswith(".bak"):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, project_dir)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
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
                    signatures.append("  - (Failed to parse AST)")
                
                summary[rel_path] = {
                    "content": content,
                    "signatures": "\n".join(signatures)
                }
    return summary

def backup_files(project_dir: str, file_list: list):
    for rel_path in file_list:
        full_path = os.path.join(project_dir, rel_path)
        if os.path.exists(full_path):
            backup_path = full_path + ".bak"
            shutil.copyfile(full_path, backup_path)
            print(f" Backed up: {rel_path} -> {rel_path}.bak")

def parse_and_apply_edits(project_dir: str, response_text: str) -> list[str]:
    pattern = r"<<<FILE:\s*(.*?)>>>\s*\n(.*?)\s*<<<END_FILE>>>"
    matches = re.findall(pattern, response_text, re.DOTALL)
    
    modified_files = []
    if matches:
        files_to_edit = [filename.strip() for filename, _ in matches]
        backup_files(project_dir, files_to_edit)

        for filename, new_code in matches:
            filename = filename.strip()
            clean_code = re.sub(r"^```(?:python)?\s*\n?", "", new_code.strip(), flags=re.IGNORECASE)
            clean_code = re.sub(r"\n?\s*```$", "", clean_code).strip()

            target_path = os.path.join(project_dir, filename)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(clean_code + "\n")
            
            print(f" Updated file: {filename}")
            modified_files.append(filename)
            
    return modified_files

def run_tests(project_dir: str, test_script: str = "test_calculator.py") -> tuple[bool, str]:
    print(f"\n Running test suite ({test_script}) in subprocess...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", test_script],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return (result.returncode == 0), output
    except Exception as e:
        return False, str(e)

def run_multi_file_agent(project_dir: str, instruction: str, test_file: str = "test_calculator.py", max_attempts: int = 3) -> bool:
    api_key = os.environ.get("GROQ_API_KEY") or "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"
    client = Groq(api_key=api_key)
    model_name = get_active_model(client)

    print("=" * 60)
    print("MULTI-FILE AGENT STARTED")
    print(f"PROJECT DIR: {project_dir}")
    print(f"INSTRUCTION: {instruction}")
    print(f"MODEL: {model_name}")
    print("=" * 60)

    repo_summary = summarize_project(project_dir)
    context_str = "PROJECT STRUCTURE & CONTENTS:\n\n"
    for file_path, data in repo_summary.items():
        context_str += f"=== FILE: {file_path} ===\n"
        context_str += f"Signatures:\n{data['signatures']}\n\n"
        context_str += f"Full Code:\n{data['content']}\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context_str}\nINSTRUCTION:\n{instruction}"}
    ]

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- [ATTEMPT {attempt}/{max_attempts}] ---")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content
        print("\n> AGENT PROPOSED EDITS:")
        print("-" * 40)
        print(response_text)
        print("-" * 40)

        modified = parse_and_apply_edits(project_dir, response_text)
        if not modified:
            print(" Warning: Agent did not produce any valid file modification blocks.")

        passed, test_output = run_tests(project_dir, test_file)
        
        if passed:
            print(f"\n ALL TESTS PASSED!")
            print(f"Test Output:\n{test_output}")
            return True
        else:
            print(f"\n TESTS FAILED!")
            print(f"Traceback:\n{test_output}")
            
            if attempt < max_attempts:
                print(f"\n Feeding error back for Attempt {attempt + 1}...")
                messages.append({"role": "assistant", "content": response_text})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The updated code failed tests with the following error:\n\n"
                        f"{test_output}\n\n"
                        f"Please fix the error and output updated code using <<<FILE: filename>>> format."
                    )
                })

    print(f"\n Agent failed after {max_attempts} attempts.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Multi-file editing agent")
    parser.add_argument("--dir", type=str, default="sample_project", help="Path to project directory")
    parser.add_argument("--task", type=str, required=True, help="Instruction for multi-file edits")
    parser.add_argument("--test-file", type=str, default="test_calculator.py", help="Test runner script")
    args = parser.parse_args()

    run_multi_file_agent(args.dir, args.task, args.test_file)

if __name__ == "__main__":
    main()