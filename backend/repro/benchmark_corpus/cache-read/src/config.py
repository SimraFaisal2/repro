"""Nested config store with a None-subscript bug.

`get_section()` returns None for a missing section, but `db_host()`
indexes into the returned section without checking — crashing when the
section does not exist yet.
"""

CONFIG = {
    "database": {"host": "localhost", "port": 5432},
    "cache": {"host": "localhost", "port": 6379},
}


def get_section(name):
    return CONFIG.get(name)


def db_host(section_name):
    section = get_section(section_name)
    return section["host"]
