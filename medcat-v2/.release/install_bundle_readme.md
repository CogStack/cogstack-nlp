# What are install bundles?

An install bundle (at least in this context) is collection of dependencies needed to use `medcat`.
This includes all direct and transitive dependencies as well as the `medcat` package itself.

The install bundle:
- Is a `.tar.gz`
- Has the naming scheme `medcat-v<MAJOR>.<MINOR>.<PATCH>-3.<PY_MINOR>-cpu.tar.gz`
  - The `<MAJOR>`, `<MINOR>`, and `<PATCH>` placeholder indicate the major, minor and patch release numbers for `medcat`
  - The `<PY_MINOR>` placeholder indicates the Python verison it was built for
- It contains
  - A collection of `.whl` files
    - These are installation files for packages
    - There's one for `medcat` itself
    - And there's one for each direct and transitive dependency
  - A `requirements.txt` file specifying the requirements installed
  - This README file

# Who are install bundles for?

Most of the time, when installing python packages, `pip` (or another similar tool) is used to install them.
It (generally) uses the Python Package Index ([PyPI](pypi.org)) to do those installs.
However, sometimes another index / mirror can be set up internally within an organisation instead.

An install bundle is designed to simplify the installation in air-gapped or semi air-gapped environments where:
- The installation environment does not have access to PyPI
- If there is a organisation-specific index / mirror it does not include all the dependencies

# What are some other benefits of install bundles

The main purpose is to help the people described in the section above.
However, there's a few other benefits:
- Using an install bundle provides a better guarantee of compatibility
  - Since we've done some (albeit limited) tests during release
  - There's a higher chance that the combination of dependencies just works
- Install bundles live forever (or at least as long as GitHub)
  - One can go back and install an older version of `medcat`
  - Even if some newer dependencies would be allowed by requirements, but those are (retroactively) incompatible
  - Even if/when some dependencies cease to exist on PyPI (are removed / deprecated)

# Who are install bundles NOT for?

Install bundles are not for
- First time users trying out `medcat`
  - You should use `pip install` (or similar) instead
- Users with full internet access
  - You should use `pip install` (or similar) instead
- Users building a service / docker image
  - Use other existing tooling

The main reason you would normally want to use existing tooling for installing `medcat` is so that it is compatible with the rest of your existing ecosystem.
If you rely too heavily on the install bundle, you might find yourself with incompatible dependencies.

# What install bundles do we provide as part of a release?

Currently we provide an install bundle for each supported python version (3.9, 3.10, 3.11, and 3.12).
These are targeting `x86_64` (think Intel and AMD CPUs) based Linux (think Ubuntu, Debian) machines.
They **do not** provide GPU enabled `torch` because the bundle would become too large to handle for a GitHub release if they did.
Users who need gpu-enabled `torch` will need to install it separately.

**The included release bundles are unlikely to work in other environments (i.e on MacOS, or Windows, or on an ARM based CPU architecture).**

# How to install an install bundle?

Once you've downloaded the install bundle on a computer with internet / PyPI access you need to
- Move the archive (a `.tar.gz` file) to the target machine
- Unarchive using `tar -xvzf medcat-v2.*-cpu.tar.gz`
  - Probably best to specify your exact file path
  - This will extract the contents (both the `.whl` files and this README) in the current folder
- Activate your virtual environment (`venv`, `conda`, etc).
  - You generally don't want to install packages for your system `python`
- Install all the wheels
  - `pip install /path/to/unarchived/bundle/*.whl`
  - NOTE: If there are other `.whl` files in the folder, this will attempt to install these as well
- Now everything should work as expected
  - You can run this to verify:
  ```
  python -c "from medcat import __version__ as v;print(f'Installed medcat v{v}')"
  ```
