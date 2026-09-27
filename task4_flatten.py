def flatten(nested_list):
    result = []
    for sublist in nested_list:
        for item in sublist:
            result.append(item)
    return result

assert flatten([[1, 2], [3, 4]]) == [1, 2, 3, 4]
assert flatten([]) == []
