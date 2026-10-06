"""Deterministic labelled grid rectangle extraction."""
def rectangles(mask):
    remaining = mask.copy()
    for i in range(mask.shape[0]):
        j = 0
        while j < mask.shape[1]:
            value = remaining[i, j]
            if not value:
                j += 1
                continue
            j1 = j+1
            while j1 < mask.shape[1] and remaining[i, j1] == value:
                j1 += 1
            i1 = i+1
            while i1 < mask.shape[0] and (remaining[i1, j:j1] == value).all():
                i1 += 1
            remaining[i:i1, j:j1] = 0
            yield i, i1, j, j1, int(value)
            j = j1
