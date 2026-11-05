"""User import parsing."""


def parse_users(rows):
    parsed = []
    for row in rows:
        try:
            parsed.append({"name": row["name"]})
        except KeyError:
            continue
    return parsed
