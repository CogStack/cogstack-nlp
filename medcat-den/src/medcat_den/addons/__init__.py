from importlib.metadata import entry_points
import sys


def _load_addons():
    version = sys.version_info.major, sys.version_info.minor
    if version >= (3, 10):
        # for python 3.10 and above
        eps = entry_points(group="medcat_den.addons")
    else:
        # for python 3.9
        eps = entry_points().get("medcat_den.addons", [])
    for ep in eps:
        ep.load()  # this should import the addon and trigger registration
