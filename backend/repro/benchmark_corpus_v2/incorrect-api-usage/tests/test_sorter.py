from src.sorter import sort_desc


def test_sort_desc():
    assert sort_desc([3, 1, 2]) == [3, 2, 1]


def test_sort_desc_single():
    assert sort_desc([5]) == [5]
