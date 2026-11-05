from src.grid import zero_grid


def test_single_row():
    grid = zero_grid(1, 3)
    grid[0][1] = 5
    assert grid == [[0, 5, 0]]


def test_single_column():
    grid = zero_grid(3, 1)
    grid[1][0] = 9
    assert grid == [[0], [9], [0]]


def test_zero_columns():
    assert zero_grid(2, 0) == [[], []]


def test_each_row_has_distinct_identity():
    grid = zero_grid(3, 1)
    assert len({id(row) for row in grid}) == 3
