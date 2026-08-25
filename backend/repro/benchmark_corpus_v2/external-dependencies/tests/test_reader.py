from src.reader import first_line


def _external_stream(lines):
    """Stands in for an external library that streams lines lazily."""
    for line in lines:
        yield line


def test_first_line_generator():
    stream = _external_stream(["hello", "world"])
    assert first_line(stream) == "hello"


def test_first_line_list():
    assert first_line(["a", "b"]) == "a"
