import sys
import pathlib
import re
from functools import partial


rel_install_path = "../medcat-v2/"
abs_install_path = str(pathlib.Path(rel_install_path).resolve())

# Matches either:
# 1. `! pip install medcat[extras]~=version`
# 2. `! pip install medcat[extras] @ git+...`
shell_pattern = re.compile(
    r'(!\s*pip\s+install\s+)'       # group 1: the install command
    r'(\\?"?)'                       # group 2: optional opening \"
    r'medcat'
    r'(\[.*?\])?'                    # group 3: optional extras
    r'(?:'
        r'\s*@\s*git\+[^"\'\s]+'
        r'|'
        r'\s*[~=!<>][^"\'\\s]*'
    r')'
    r'(\\?"?)'                       # group 4: optional closing \"
)
req_txt_pattern = re.compile(
    r'^(medcat(\[.*?\])?)\s*@\s*git\+\S+', flags=re.MULTILINE
)


def repl_nb(m, file_path: pathlib.Path):
    extras = m[3] or ""
    to_write = f'! pip install \\"{abs_install_path}{extras}\\"'
    print(f"[PATCHED] {file_path}\n with: '{to_write}'")
    return to_write


def do_patch(nb_path: pathlib.Path,
             regex: re.Pattern = shell_pattern, repl_method=repl_nb):
    nb_text = nb_path.read_text(encoding="utf-8")

    repl = partial(repl_method, file_path=nb_path)
    new_text = regex.sub(repl, nb_text)

    if nb_text != new_text:
        nb_path.write_text(new_text, encoding="utf-8")


def main(path: str):
    for nb_path in pathlib.Path(path).rglob("**/*.ipynb"):
        do_patch(nb_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python patch_notebook_installs.py <path>")
        sys.exit(1)

    path = sys.argv[1]

    if not pathlib.Path(path).exists():
        print(f"Path {path} does not exist.")
        sys.exit(1)

    main(path)