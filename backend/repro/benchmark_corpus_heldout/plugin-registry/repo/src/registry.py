"""Plugin registry."""

from src.plugins.alpha import NAME, run

PLUGINS = {"alpha": run}


def get(name):
    return PLUGINS[name]
