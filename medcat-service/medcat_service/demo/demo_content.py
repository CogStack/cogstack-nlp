import importlib.resources
from functools import cache


@cache
def _read_file(filename: str) -> str:
    package = importlib.resources.files(__package__ or 'medcat_service.demo')
    file_path = package / 'resources' / filename
    return file_path.read_text(encoding='utf-8')


short_example = _read_file('short_example.txt')
long_example = _read_file('long_example.txt')
anoncat_example = _read_file('anoncat_example.txt')
article_footer = _read_file('article_footer.txt')
anoncat_help_content = _read_file('anoncat_help_content.txt')
