# Releases

The scripts within here are designed to help preparing for and dealing with releases.

The main idea is to use the `prepare_release.sh` script from within the root of the project and it will delegate either to `prepare_minor_release.sh` or `prepare_patch_release.sh` as necessary.
The workflow within the scripts is as follows:
- Create or check out release branch (`medcat/v<major>.<minor>`)
- Update version in `pyproject.toml`
- Create a tag based on the version
  - This will be in the format `medcat/v<major>.<minor>.<patch>`
- Push both the branch as well as the tag to `origin`

The general usage for a minor release based on the `main` branch from within the **root of the project** is simply:
```
bash .release/prepare_release.sh <major>.<minor>.0
```
and the usage for a patch release (from within the **root of the project**) is in the format
```
bash .release/prepare_release.sh <major>.<minor>.<patch> <hash 1> <hash 2> ...
```
where `hash 1` and `hash 2` (and so on) refer to the commit hashes that need to be included / cherry-picked in the patch release.

