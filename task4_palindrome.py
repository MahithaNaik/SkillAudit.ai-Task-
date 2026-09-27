def is_palindrome(s: str) -> bool:
    cleaned = ''.join(ch.lower() for ch in s if not ch.isspace())
    return cleaned == cleaned[::-1]
