import os
import re
import sys
import argparse
from groq import Groq

SYSTEM_PROMPT = (
    "You are an automated Python code generator. "
    "Your output MUST contain ONLY valid, executable Python code. "
    "Do NOT include any explanations, markdown code blocks, backticks (```), "
    "introductory text, or conversational commentary. Output raw code only."
)

def strip_code_fences(text: str) -> str:
    """Removes ```python and ``` formatting if the AI includes it."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?\s*```$", "", text)
    return text.strip()

def get_active_model(client: Groq) -> str:
    """Finds an active text generation model on Groq while ignoring security/audio models."""
    try:
        available_models = [m.id for m in client.models.list().data]
        
        ignored_keywords = ["guard", "whisper", "vision", "embed", "safeguard"]
        valid_models = [
            m for m in available_models 
            if not any(keyword in m.lower() for keyword in ignored_keywords)
        ]
        
        for m in valid_models:
            if any(name in m.lower() for name in ["llama-3.3", "llama-3.1", "qwen", "mixtral", "gemma"]):
                return m
                
        return valid_models[0] if valid_models else "llama-3.3-70b-versatile"
    except Exception:
        return "llama-3.3-70b-versatile"

def generate_code(task: str) -> str:
    client = Groq(api_key="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")
    
    model_name = get_active_model(client)
    print(f"Using active model: {model_name}")

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task}
        ],
        temperature=0.1,
    )
    
    raw_output = response.choices[0].message.content
    return strip_code_fences(raw_output)

def main():
    parser = argparse.ArgumentParser(description="CLI Tool to generate Python code.")
    parser.add_argument("task", type=str, help="Plain English description of the coding task")
    parser.add_argument("-o", "--output", type=str, default="generated_code.py", help="File path to save code")
    
    args = parser.parse_args()

    print(f"Task: {args.task}")
    print("Asking Groq to write code...\n")
    
    try:
        code = generate_code(args.task)
        
        print("=" * 40)
        print(code)
        print("=" * 40 + "\n")
        
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(code + "\n")
            
        print(f"Success! Code saved to '{args.output}'")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()