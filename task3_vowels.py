def count_vowels(s: str) -> int:
    vowels = 'aeiouAEIOU'
    return sum(1 for char in s if char in vowels)

assert count_vowels('Hello World') == 3
assert count_vowels('xyz') == 0
