import importlib.resources
from functools import cache
from pathlib import Path

from medcat_service.config import Settings


@cache
def _read_file(filename: str) -> str:
    package = importlib.resources.files(__package__ or 'medcat_service.demo')
    file_path = package / 'resources' / filename
    return file_path.read_text(encoding='utf-8')


short_example = _read_file('short_example.txt')
long_example = _read_file('long_example.txt')
anoncat_example = _read_file('anoncat_example.txt')
default_footer = _read_file('default_footer.md')


def resolve_demo_markdown(settings: Settings) -> str:
    """Return custom demo markdown when a path is set, otherwise the bundled default."""
    path = settings.demo_ui_custom_markdown_path
    if not path:
        return default_footer
    return Path(path).read_text(encoding="utf-8")
