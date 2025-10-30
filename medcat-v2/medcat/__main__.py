import sys


_CLI_USAGE = (
    "Usage: python -m medcat download-scripts [DEST] [log_level]"
    # NOTE: if there are more options, add them
)


def main(*args: str):
    if not args:
        print(_CLI_USAGE, file=sys.stderr)
        sys.exit(1)
    if len(args) >= 1 and args[0] == "download-scripts":
        from medcat.utils.download_scripts import main as download_scripts
        download_scripts(*args[1:])
    else:
        print(_CLI_USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
