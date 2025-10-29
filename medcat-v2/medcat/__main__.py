import sys


def main(*args: str):
    if not args:
        print("Usage: python -m medcat download-scripts [DEST] [log_level]",
              file=sys.stderr)
        sys.exit(1)
    if len(args) >= 1 and args[0] == "download-scripts":
        from medcat.utils.download_scripts import main
        dest = args[1] if len(args) > 1 else "."
        kwargs = {}
        if len(args) > 2:
            kwargs["log_level"] = args[2].upper()
        main(dest, **kwargs)
    else:
        print("Usage: python -m medcat download-scripts [DEST]",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
