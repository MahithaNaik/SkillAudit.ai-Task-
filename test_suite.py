import subprocess

test_tasks = [
    
    ("write a function that checks if a number is prime", "task1_prime.py"),
    ("write a function to return the nth Fibonacci number using recursion with memoization", "task2_fibonacci.py"),
    ("write a function that computes the greatest common divisor (GCD) of two numbers without math library", "task3_gcd.py"),
    
    ("write a function that checks if a string is a palindrome ignoring spaces and case", "task4_palindrome.py"),
    ("write a function that counts vowels and consonants in a string and returns a tuple", "task5_vowels.py"),
    ("write a function that reverses each word in a given sentence while maintaining word order", "task6_reverse_words.py"),
 
    ("write a function that merges two dictionaries and sums the values for overlapping keys", "task7_dict_merge.py"),
    ("write a function that takes a list of integers and returns the top K most frequent elements", "task8_top_k.py"),
]

for task, filename in test_tasks:
    print(f"Running task: {task}")
    subprocess.run(["python", "codegen.py", task, "-o", filename])
    print("-" * 50)