import sys
import pathlib
import re
from functools import partial


repo_url = "git+https://github.com/CogStack/cogstack-nlp"

# Matches either:
# 1. `! pip install medcat[extras]`
# 2. `! pip install medcat[extras] @ git+...`
shell_pattern = re.compile(
    r'(!\s*pip\s+install\s+)(\\["\']?)medcat(\[.*?\])'
    r'(\s*@\s*git\+[^"\'\s]+)?\2'
)
req_txt_pattern = re.compile(
    r'^(medcat(\[.*?\])?)\s*@\s*git\+\S+', flags=re.MULTILINE
)


def repl_nb(m, file_path: pathlib.Path, branch: str):
    extras = m[3]
    old_url = m[4]
    if old_url and "medcat/v" in old_url:
        print(f"[WARN] {file_path} refers to alpha/tagged release: "
              f"{old_url.strip()}")
    return (f'{m[1]}\\"medcat{extras} @ {repo_url}@{branch}'
            '#subdirectory=medcat-v2\\"')


def repl_req(m, file_path: pathlib.Path, branch: str):
    extras = m[2] if m[2] else ""
    return (f"medcat{extras} @ {repo_url}@{branch}"
            "#subdirectory=medcat-v2")


def do_patch(nb_path: pathlib.Path, branch: str,
             regex: re.Pattern = shell_pattern, repl_method=repl_nb):
    nb_text = nb_path.read_text(encoding="utf-8")

    repl = partial(repl_method, file_path=nb_path, branch=branch)
    new_text = regex.sub(repl, nb_text)

    if nb_text != new_text:
        nb_path.write_text(new_text, encoding="utf-8")
        print(f"[PATCHED] {nb_path}")


def main(path: str, branch: str):
    for nb_path in pathlib.Path(path).rglob("**/*.ipynb"):
        do_patch(nb_path, branch)

    # Patch requirements.txt as well
    do_patch(pathlib.Path(path, "requirements.txt"), branch,
             regex=req_txt_pattern, repl_method=repl_req)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python patch_notebooks_and_requirements.py "
              "<path> <branch>")
        sys.exit(1)

    path = sys.argv[1]
    branch = sys.argv[2]

    if not pathlib.Path(path).exists():
        print(f"Path {path} does not exist.")
        sys.exit(1)

    main(path, branch)
