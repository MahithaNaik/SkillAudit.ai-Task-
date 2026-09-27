def reverse_words_in_sentence(sentence: str) -> str:
    """
    Reverses each word in a given sentence while maintaining word order.
    
    Args:
        sentence: A string containing words separated by spaces.
        
    Returns:
        A string where each word is reversed, but the word order is preserved.
    """
    words = sentence.split(' ')
    reversed_words = [word[::-1] for word in words]
    return ' '.join(reversed_words)
