import sys as __sys

if __name__ == "__main__":
    argv = __sys.argv.copy()
    if "--with-injection" in argv:
        argv.pop(argv.index("--with-injection"))
        from .injection import run_with_injection
        run_with_injection(argv[1], argv[2:])
    else:
        raise ValueError("Only --with-injection is a valid entrypoint")
