import subprocess
import sys
import os


TARGET_FILE = os.path.join(
    os.path.dirname(__file__), "_test_runtime_injection.py")
ROOT_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", ".."))


def help_check(run_args: list[str], force_here: bool = False):
    result = subprocess.run(run_args, check=True, text=True,
                            capture_output=True)
    out_text = result.stdout
    assert "METHOD: functools.partial" in out_text
    assert "function injected_load_model_pack" in out_text


def test_runtime_injection_file_path():
    run_args = [sys.executable, '-m', 'medcat_den', '--with-injection',
                TARGET_FILE]
    help_check(run_args)


def test_runtime_injection_module_path():
    rel_path = TARGET_FILE.removeprefix(ROOT_PATH)
    target_module = rel_path.removesuffix(
        # NOTE: avoid ending .py, replace / with . and remove starting .
        ".py").replace(os.path.sep, ".").removeprefix(".")
    run_args = [sys.executable, '-m', 'medcat_den', '--with-injection',
                "-m", target_module]
    help_check(run_args)


def test_runtime_injection_code_snippet():
    with open(TARGET_FILE) as f:
        contents = f.readlines()
    cmd = ";".join([sline for line in contents
                    if (sline := line.strip())])
    run_args = [sys.executable, '-m', 'medcat_den', '--with-injection',
                "-c", cmd]
    help_check(run_args)
