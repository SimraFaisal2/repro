"""Integer parsing helper."""


def parse(text):
    try:
        return int(text)
    except ValueError:
        return 0
