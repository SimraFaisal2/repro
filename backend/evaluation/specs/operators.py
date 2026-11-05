"""Held-out wrong-operator / wrong-comparison cases (5)."""

CASES = [
    {
        "id": "discount-threshold",
        "name": "Discount excludes exactly 100",
        "category": "wrong-operator",
        "difficulty": "easy",
        "root_cause_file": "src/pricing.py",
        "root_cause_line": 4,
        "hidden_bug": "discount() uses `total > 100` instead of `total >= 100`, so an order "
                       "of exactly 100 misses the advertised discount.",
        "expected_behavior": "discount(100) returns 90.0; discount(99.99) returns 99.99.",
        "ground_truth_summary": "Use >= in the threshold comparison.",
        "files": {
            "src/pricing.py": '''"""Order discount calculation."""


def discount(total):
    if total > 100:
        return round(total * 0.9, 2)
    return total
''',
            "tests/test_pricing.py": '''from src.pricing import discount


def test_exact_threshold():
    assert discount(100) == 90.0


def test_below_threshold():
    assert discount(50) == 50


def test_above_threshold():
    assert discount(150) == 135.0
''',
        },
        "fixed": {
            "src/pricing.py": '''"""Order discount calculation."""


def discount(total):
    if total >= 100:
        return round(total * 0.9, 2)
    return total
''',
        },
        "oracle": '''from src.pricing import discount


def test_just_below():
    assert discount(99.99) == 99.99


def test_just_above():
    assert discount(100.01) == 90.01


def test_zero():
    assert discount(0) == 0


def test_two_decimals():
    assert discount(123.45) == 111.11
''',
    },
    {
        "id": "retry-limit",
        "name": "Retry predicate compares in the wrong direction",
        "category": "wrong-operator",
        "difficulty": "easy",
        "root_cause_file": "src/retries.py",
        "root_cause_line": 4,
        "hidden_bug": "can_retry() returns attempts > limit instead of attempts < limit, so it "
                       "allows retries after the limit and blocks the first attempt.",
        "expected_behavior": "can_retry(0, 3) is True and can_retry(3, 3) is False.",
        "ground_truth_summary": "Compare attempts < limit.",
        "files": {
            "src/retries.py": '''"""Retry policy."""


def can_retry(attempts, limit):
    return attempts > limit
''',
            "tests/test_retries.py": '''from src.retries import can_retry


def test_first_attempt():
    assert can_retry(0, 3) is True


def test_at_limit():
    assert can_retry(3, 3) is False


def test_over_limit():
    assert can_retry(4, 3) is False
''',
        },
        "fixed": {
            "src/retries.py": '''"""Retry policy."""


def can_retry(attempts, limit):
    return attempts < limit
''',
        },
        "oracle": '''from src.retries import can_retry


def test_zero_limit():
    assert can_retry(0, 0) is False


def test_negative_limit():
    assert can_retry(0, -1) is False


def test_one_below():
    assert can_retry(2, 3) is True


def test_returns_bool():
    assert can_retry(0, 1) is True
''',
    },
    {
        "id": "temperature-range",
        "name": "Temperature check uses an impossible chained comparison",
        "category": "wrong-operator",
        "difficulty": "medium",
        "root_cause_file": "src/climate.py",
        "root_cause_line": 4,
        "hidden_bug": "in_range() evaluates `-40 < t > 125`, which can never be true, instead "
                       "of checking that t lies between the inclusive bounds.",
        "expected_behavior": "in_range(20) is True; both -40 and 125 are inclusive.",
        "ground_truth_summary": "Use -40 <= t <= 125.",
        "files": {
            "src/climate.py": '''"""Operating temperature range."""


def in_range(t):
    return -40 < t > 125
''',
            "tests/test_climate.py": '''from src.climate import in_range


def test_normal():
    assert in_range(20) is True


def test_too_hot():
    assert in_range(150) is False


def test_too_cold():
    assert in_range(-50) is False
''',
        },
        "fixed": {
            "src/climate.py": '''"""Operating temperature range."""


def in_range(t):
    return -40 <= t <= 125
''',
        },
        "oracle": '''from src.climate import in_range


def test_lower_bound():
    assert in_range(-40) is True


def test_upper_bound():
    assert in_range(125) is True


def test_just_outside():
    assert in_range(-41) is False
    assert in_range(126) is False


def test_zero():
    assert in_range(0) is True
''',
    },
    {
        "id": "password-length",
        "name": "Password minimum is off by one",
        "category": "wrong-operator",
        "difficulty": "easy",
        "root_cause_file": "src/auth.py",
        "root_cause_line": 4,
        "hidden_bug": "valid_password() requires len(password) > 8, rejecting the documented "
                       "eight-character minimum.",
        "expected_behavior": "valid_password('12345678') is True; seven characters is False.",
        "ground_truth_summary": "Use >= 8.",
        "files": {
            "src/auth.py": '''"""Password policy."""


def valid_password(password):
    return len(password) > 8
''',
            "tests/test_auth.py": '''from src.auth import valid_password


def test_exact_minimum():
    assert valid_password("12345678") is True


def test_longer():
    assert valid_password("123456789") is True


def test_too_short():
    assert valid_password("1234567") is False
''',
        },
        "fixed": {
            "src/auth.py": '''"""Password policy."""


def valid_password(password):
    return len(password) >= 8
''',
        },
        "oracle": '''from src.auth import valid_password


def test_empty():
    assert valid_password("") is False


def test_unicode_length():
    assert valid_password("pässwörd") is True


def test_no_whitespace_stripping():
    assert valid_password("        ") is True


def test_one_character():
    assert valid_password("x") is False
''',
    },
    {
        "id": "grade-boundaries",
        "name": "Grade boundaries use strict comparisons",
        "category": "wrong-operator",
        "difficulty": "medium",
        "root_cause_file": "src/grades.py",
        "root_cause_line": 5,
        "hidden_bug": "grade() uses `score > 90` and `score > 80`, so exactly 90 is a B and "
                       "exactly 80 is a C, contradicting the published cutoffs.",
        "expected_behavior": "90 is an A, 80 is a B, 70 is a C, and 69 is an F.",
        "ground_truth_summary": "Make the A and B comparisons inclusive.",
        "files": {
            "src/grades.py": '''"""Letter grades."""


def grade(score):
    if score > 90:
        return "A"
    if score > 80:
        return "B"
    if score >= 70:
        return "C"
    return "F"
''',
            "tests/test_grades.py": '''from src.grades import grade


def test_ninety():
    assert grade(90) == "A"


def test_eighty():
    assert grade(80) == "B"


def test_seventy():
    assert grade(70) == "C"


def test_sixty_nine():
    assert grade(69) == "F"
''',
        },
        "fixed": {
            "src/grades.py": '''"""Letter grades."""


def grade(score):
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    return "F"
''',
        },
        "oracle": '''from src.grades import grade


def test_perfect():
    assert grade(100) == "A"


def test_just_below_a():
    assert grade(89.9) == "B"


def test_just_below_b():
    assert grade(79.9) == "C"


def test_just_below_c():
    assert grade(69.9) == "F"


def test_zero():
    assert grade(0) == "F"
''',
    },
]
