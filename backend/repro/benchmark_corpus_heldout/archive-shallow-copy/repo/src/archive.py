"""Archive rows."""


def archive(rows):
    copied = list(rows)
    for row in copied:
        row["archived"] = True
    return copied
