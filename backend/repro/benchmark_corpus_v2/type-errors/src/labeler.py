"""Label builder. Concatenates a count onto a string, but the count is an
int — TypeError at runtime."""


def build_label(count):
    return "Total: " + count
