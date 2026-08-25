"""Descending sort. list.sort() sorts in place and returns None, but the
result of that call is returned as if it were the sorted list."""


def sort_desc(values):
    return values.sort(reverse=True)
