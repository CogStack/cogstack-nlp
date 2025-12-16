from importlib.metadata import entry_points


ENTRY_POINT_PATH = "medcat.plugins"


def load_plugins():
    eps = entry_points(group=ENTRY_POINT_PATH)
    for ep in eps:
        # this will init the addon
        ep.load()
