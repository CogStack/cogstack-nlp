import sys
from medcat.utils.download_scripts import main as __download_scripts


_COMMANDS = {
    "download-scripts": __download_scripts
}


def _get_usage() -> str:
    header = "Available commands:\n"
    base = "python -m medcat "
    args = " --help"
    commands = [base + cmd_name + args
                for cmd_name in _COMMANDS]
    return header + "\n".join(commands)


def main(*args: str):
    if not args or args[0] not in _COMMANDS:
        print(_get_usage(), file=sys.stderr)
        sys.exit(1)
    _COMMANDS[args[0]](*args[1:])


if __name__ == "__main__":
    main(*sys.argv[1:])
