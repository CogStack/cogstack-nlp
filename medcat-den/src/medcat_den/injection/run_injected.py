import sys
import runpy
import code

from medcat_den.injection import injected_den


def _run_code(target: str, args: list[str]):
    if target.endswith(".py"):
        # Run the target script (like python target.py)
        sys.argv = [target] + args
        runpy.run_path(target, run_name="__main__")
    elif target == "-c":
        exec(" ".join(args))
    elif target == "-m":
        true_target, args = args[0], args[1:]
        sys.argv = [true_target] + args
        # Run the target module in __main__ context (like python -m target)
        runpy.run_module(true_target, run_name="__main__")


def _do_interactive(args: list[str]):
    if args:
        true_target, args = args[0], args[1:]
        _run_code(true_target, args)
    code.interact(local={"__name__": "__main__"})


def run_with_injection(target: str, args: list[str]):
    # Prepare sys.argv for the target module
    with injected_den():
        if target.endswith(".py") or target in ("-c", "-m"):
            _run_code(target, args)
        elif target == '-i':
            _do_interactive(args)
        else:
            raise ValueError(f"Unknown target: {target} (args: {args})")
