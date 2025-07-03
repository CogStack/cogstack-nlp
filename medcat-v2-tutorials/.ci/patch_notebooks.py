import sys
import pathlib
import re

branch = sys.argv[1]
repo_url = "git+https://github.com/CogStack/cogstack-nlp"

# Matches either:
# 1. `! pip install medcat[extras]`
# 2. `! pip install medcat[extras] @ git+...`
shell_pattern = re.compile(
    r'(!\s*pip\s+install\s+)(\\["\']?)medcat(\[.*?\])(\s*@\s*git\+[^"\'\s]+)?\2'
)

for nb_path in pathlib.Path(".").rglob("notebooks/**/*.ipynb"):
    nb_text = nb_path.read_text(encoding="utf-8")

    def repl(m):
        extras = m[3]
        old_url = m[4]
        if old_url and "medcat/v" in old_url:
            print(f"[WARN] {nb_path} refers to alpha/tagged release: {old_url.strip()}")
        return f'{m[1]}\\"medcat{extras} @ {repo_url}@{branch}#subdirectory=medcat-v2\\"'

    new_text = shell_pattern.sub(repl, nb_text)

    if nb_text != new_text:
        nb_path.write_text(new_text, encoding="utf-8")
        print(f"[PATCHED] {nb_path}")
