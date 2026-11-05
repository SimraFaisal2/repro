"""Runtime configuration helpers."""


def timeout(config):
    return config.get("timeout", 30)
