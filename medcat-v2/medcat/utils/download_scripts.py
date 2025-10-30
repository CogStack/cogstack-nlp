"""This module is designed to identify and download the medcat-scripts.

It will link the current setup (i.e medcat version) into account and
subsequently identify and download the medcat-scripts based on the most
recent applicable tag. So if you've got medcat==2.2.0, it might grab
medcat/v2.2.3 for instance.
"""
import importlib.metadata
import tempfile
import zipfile
from pathlib import Path
import requests
import logging
import argparse


logger = logging.getLogger(__name__)


EXPECTED_TAG_PREFIX = 'medcat/v'
GITHUB_REPO = "CogStack/cogstack-nlp"
SCRIPTS_PATH = "medcat-scripts/"
DOWNLOAD_URL_TEMPLATE = (
    f"https://api.github.com/repos/{GITHUB_REPO}/zipball/{{tag}}"
)


def _get_medcat_version() -> str:
    """Return the installed MedCAT version as 'major.minor'."""
    version = importlib.metadata.version("medcat")
    major, minor, *_ = version.split(".")
    minor_version = f"{major}.{minor}"
    logger.debug("Using medcat minor version of %s", minor_version)
    return minor_version


def _find_latest_scripts_tag(major_minor: str) -> str:
    """Query for the newest medcat-scripts tag matching 'v{major_minor}.*'."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
    tags = requests.get(url, timeout=15).json()

    matching = [
        t["name"]
        for t in tags
        if t["name"].startswith(f"{EXPECTED_TAG_PREFIX}{major_minor}.")
    ]
    logger.debug("Found %d matching (out of a total of %d): %s",
                 len(matching), len(tags), matching)
    if not matching:
        raise RuntimeError(
            f"No medcat-scripts tags found for MedCAT {major_minor}.x")

    # Tags are returned newest first by GitHub
    return matching[0]


def _determine_url(overwrite_url: str | None,
                   overwrite_tag: str | None) -> str:
    if overwrite_url:
        logger.info("Using the overwrite URL instead: %s", overwrite_url)
        zip_url = overwrite_url
    else:
        version = _get_medcat_version()
        if overwrite_tag:
            tag = overwrite_tag
            logger.info("Using overwritten tag '%s'", tag)
        else:
            tag = _find_latest_scripts_tag(version)

        logger.info("Fetching scripts for MedCAT %s → tag %s}",
                    version, tag)

        # Download the GitHub auto-generated zipball
        zip_url = DOWNLOAD_URL_TEMPLATE.format(tag=tag)
    return zip_url


def _download_zip(zip_url: str, tmp: tempfile._TemporaryFileWrapper):
    with requests.get(zip_url, stream=True, timeout=30) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.flush()


def _extract_zip(dest: Path, zip_path: Path):
    # Extract only medcat-scripts/ from the archive
    wrote_files_num = 0
    total_files = 0
    with zipfile.ZipFile(zip_path) as zf:
        for m in zf.namelist():
            total_files += 1
            if f"/{SCRIPTS_PATH}" not in m:
                continue
            # skip repo-hash prefix
            target = dest / Path(*Path(m).parts[2:])
            if m.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                with open(target, "wb") as f:
                    f.write(zf.read(m))
                wrote_files_num += 1

    logger.debug("Wrote %d / %d files", wrote_files_num, total_files)
    if not wrote_files_num:
        logger.warning(
            "Was unable to extract any files from '%s' folder in the zip. "
            "The folder doesn't seem to exist in the provided archive.",
            SCRIPTS_PATH)
    logger.info("Scripts extracted to: %s", dest)


def fetch_scripts(destination: str | Path = ".",
                  overwrite_url: str | None = None,
                  overwrite_tag: str | None = None) -> Path:
    """Download the latest compatible medcat-scripts folder into.

    Args:
        destination (str | Path): The destination path. Defaults to ".".
        overwrite_url (str | None): The overwrite URL. Defaults to None.
        overwrite_tag (str | None): The overwrite tag. Defaults to None.

    Returns:
        Path: The path of the scripts.
    """
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    zip_url = _determine_url(overwrite_url, overwrite_tag)
    with tempfile.NamedTemporaryFile() as tmp:
        _download_zip(zip_url, tmp)
        _extract_zip(dest, Path(tmp.name))
    return dest


def main(*in_args: str):
    parser = argparse.ArgumentParser(
        prog="python -m medcat download-scripts",
        description="Download medcat-scripts"
    )
    parser.add_argument("destination", type=str, default=".", nargs='?',
                        help="The destination folder for the scripts")
    parser.add_argument("--overwrite-url", type=str, default=None,
                        help="The URL to download and extract from. "
                             "This is expected to refer to a .zip file "
                             "that has a `medcat-scripts` folder.")
    parser.add_argument("--overwrite-tag", '-t', type=str, default=None,
                        help="The tag to use from GitHub")
    parser.add_argument("--log-level", type=str, default='INFO',
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="The log level for fetching")
    args = parser.parse_args(in_args)
    log_level = args.log_level
    logger.setLevel(log_level)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    fetch_scripts(args.destination, args.overwrite_url,
                  args.overwrite_tag)
