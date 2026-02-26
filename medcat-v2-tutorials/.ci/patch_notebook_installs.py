import sys
import pathlib
import re
from functools import partial
import argparse


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
    # only match \" (escaped quote), never a bare "
    r'(\\")?'        # group 4: optional closing \"
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
             regex: re.Pattern = shell_pattern,
             repl_method=repl_nb) -> bool:
    nb_text = nb_path.read_text(encoding="utf-8")

    repl = partial(repl_method, file_path=nb_path)
    new_text = regex.sub(repl, nb_text)

    if nb_text != new_text:
        nb_path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main(path: str, expect_min_changes: int):
    total_changes = 0
    for nb_path in pathlib.Path(path).rglob("**/*.ipynb"):
        if do_patch(nb_path):
            total_changes += 1
    if expect_min_changes >= 0 and total_changes < expect_min_changes:
        print(f"Expected a minimum of {expect_min_changes} changes,"
              f"but only found {total_changes} changes. "
              "This will force a non-zero exit status so GHA workflow "
              "can fail")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="The path to start looking at",
                        type=str)
    parser.add_argument("--expect-min-changes", "-c",
                        help="Expect at lest this number of chagnes",
                        type=int, default=-1)
    args = parser.parse_args()

    path = args.path

    if not pathlib.Path(path).exists():
        print(f"Path {path} does not exist.")
        sys.exit(1)

    main(path, args.expect_min_changes)
