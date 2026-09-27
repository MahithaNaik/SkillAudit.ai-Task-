import os
import re
import sys
import tempfile
import subprocess
import argparse
from groq import Groq

SYSTEM_PROMPT = (
    "You are an autonomous Python coding agent. "
    "Your output MUST contain ONLY valid, executable Python code. "
    "Do NOT include explanations, markdown code blocks, backticks (```), "
    "or conversational text. "
    "Make sure any requested test assertions (e.g., assert ...) are included at the bottom of the script "
    "so that running the file verifies correctness."
)

def strip_code_fences(text: str) -> str:
    """Removes markdown code fences if generated."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?\s*```$", "", text)
    return text.strip()

def get_active_model(client: Groq) -> str:
    """Selects an active text generation model on Groq."""
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

def execute_code_safely(code: str, timeout: int = 5) -> tuple[bool, str]:
    """
    Executes Python code safely in an isolated subprocess with a timeout.
    Returns (success_boolean, output_or_error_message).
    """

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
        temp_file.write(code)
        temp_filepath = temp_file.name

    try:
        result = subprocess.run(
            [sys.executable, temp_filepath],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            output = result.stdout.strip() or "Code executed successfully with zero errors."
            return True, output
        else:
            # Code failed with exception or assertion error
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown Execution Error"
            return False, error_msg

    except subprocess.TimeoutExpired:
        return False, f"ExecutionTimedOutError: Code execution exceeded safety limit of {timeout} seconds."
    except Exception as e:
        return False, f"System Execution Error: {str(e)}"
    finally:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

def run_agent_loop(task_description: str, output_file: str = "solution.py", max_attempts: int = 3) -> bool:
    """The Core Agent Loop: Generate -> Execute -> Observe -> Self-Correct."""
    client = Groq(api_key="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")
    model_name = get_active_model(client)

    print("\n" + "=" * 60)
    print(f"TASK: {task_description}")
    print(f"MODEL: {model_name}")
    print("=" * 60)

    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Write Python code for the following task:\n{task_description}"}
    ]

    for attempt in range(1, max_attempts + 1):
        print(f"\n--- [ATTEMPT {attempt}/{max_attempts}] ---")
        
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1
        )
        
        raw_code = response.choices[0].message.content
        code = strip_code_fences(raw_code)

        print("\n> GENERATED CODE:")
        print("-" * 40)
        print(code)
        print("-" * 40)

        
        print("\n> EXECUTING IN SUBPROCESS...")
        success, output = execute_code_safely(code, timeout=5)

        if success:
            print(f" STATUS: PASSED")
            print(f" OUTPUT: {output}")
            
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(code + "\n")
            print(f"\n Successfully saved verified code to '{output_file}'")
            return True
        else:
            print(f" STATUS: FAILED")
            print(f" ERROR TRACEBACK:\n{output}")
            
            
            if attempt < max_attempts:
                print(f"\n Feeding error back to LLM for Attempt {attempt + 1}...")
                
                # Append previous code and error into memory
                messages.append({"role": "assistant", "content": code})
                messages.append({
                    "role": "user", 
                    "content": (
                        f"The code you provided failed execution with the following error:\n\n"
                        f"{output}\n\n"
                        f"Please fix the error and return ONLY the corrected, complete Python code."
                    )
                })

    print(f"\n Agent failed to solve task after {max_attempts} attempts.")
    return False

def main():
    parser = argparse.ArgumentParser(description="Self-Correcting Coding Agent Loop")
    parser.add_argument("task", type=str, help="Plain English task description with assertions")
    parser.add_argument("-o", "--output", type=str, default="solution.py", help="Output file path")
    args = parser.parse_args()

    run_agent_loop(args.task, args.output)

if __name__ == "__main__":
    main()