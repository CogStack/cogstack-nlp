import sys


_DL_SCRIPTS_USAGE = (
    "Usage: python -m medcat download-scripts [DEST] [log_level]")


def main(*args: str):
    if not args:
        print(_DL_SCRIPTS_USAGE, file=sys.stderr)
        sys.exit(1)
    if len(args) >= 1 and args[0] == "download-scripts":
        from medcat.utils.download_scripts import main
        dest = args[1] if len(args) > 1 else "."
        kwargs = {}
        if len(args) > 2:
            kwargs["log_level"] = args[2].upper()
        main(dest, **kwargs)
    else:
        print(_DL_SCRIPTS_USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
