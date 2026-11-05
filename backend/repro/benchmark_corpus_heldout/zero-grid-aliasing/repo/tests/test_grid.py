from src.grid import zero_grid


def test_dimensions():
    grid = zero_grid(3, 2)
    assert len(grid) == 3
    assert all(len(row) == 2 for row in grid)


def test_rows_are_independent():
    grid = zero_grid(2, 2)
    grid[0][0] = 1
    assert grid == [[1, 0], [0, 0]]


def test_zero_rows():
    assert zero_grid(0, 3) == []
