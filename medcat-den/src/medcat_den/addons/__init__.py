from importlib.metadata import entry_points


def _load_addons():
    eps = entry_points(group="medcat_den.addons")
    for ep in eps:
        ep.load()  # this should import the addon and trigger registration
