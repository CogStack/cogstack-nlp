import sys


def main(*args: str):
    if not args:
        print("Usage: python -m medcat download-scripts [DEST]",
              file=sys.stderr)
        sys.exit(1)
    if len(args) >= 1 and args[0] == "download-scripts":
        from medcat.utils.download_scripts import fetch_scripts
        dest = args[1] if len(args) > 1 else "."
        fetch_scripts(dest)
    else:
        print("Usage: python -m medcat download-scripts [DEST]",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main(*sys.argv[1:])
