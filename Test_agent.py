from agent_loop import run_agent_loop


tasks = [
    (
        "Write a function `reverse_string(s: str) -> str` that reverses a string. "
        "Include test assertions: assert reverse_string('abc') == 'cba' and assert reverse_string('hello') == 'olleh'",
        "task1_reverse.py"
    ),
    (
        "Write a function `is_prime(n: int) -> bool` that checks if a number is prime. "
        "Include test assertions: assert is_prime(7) == True and assert is_prime(4) == False and assert is_prime(1) == False",
        "task2_prime.py"
    ),
    (
        "Write a function `count_vowels(s: str) -> int` that counts vowels in a string (case-insensitive). "
        "Include test assertions: assert count_vowels('Hello World') == 3 and assert count_vowels('xyz') == 0",
        "task3_vowels.py"
    ),
    (
        "Write a function `flatten(nested_list)` that flattens a 2D list into a 1D list. "
        "Include test assertions: assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4] and assert flatten([]) == []",
        "task4_flatten.py"
    ),
    (
        "Write a function `fibonacci(n: int) -> int` that returns the nth Fibonacci number. "
        "Include test assertions: assert fibonacci(0) == 0 and assert fibonacci(1) == 1 and assert fibonacci(10) == 55",
        "task5_fibonacci.py"
    )
]

print("=" * 60)
print("STARTING TEST SUITE FOR SELF-CORRECTING CODING AGENT")
print("=" * 60)

passed_count = 0
for idx, (task_desc, out_file) in enumerate(tasks, 1):
    print(f"\n>>> RUNNING TEST TASK {idx}/5 <<<")
    success = run_agent_loop(task_desc, output_file=out_file, max_attempts=3)
    if success:
        passed_count += 1

print("\n" + "=" * 60)
print(f"FINAL RESULTS: {passed_count}/{len(tasks)} Tasks Passed Successfully!")
print("=" * 60)