from src.labeler import build_label


def test_build_label():
    assert build_label(3) == "Total: 3"


def test_build_label_zero():
    assert build_label(0) == "Total: 0"
