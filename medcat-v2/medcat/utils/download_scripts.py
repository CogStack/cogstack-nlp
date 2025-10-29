"""This module is designed to identify and download the medcat-scripts.

It will link the current setup (i.e medcat version) into account and
subsequently identify and download the medcat-scripts based on the most
recent applicable tag. So if you've got medcat==2.2.0, it might grab
medcat-scripts/v2.2.3 for instance.
"""
import importlib.metadata
import tempfile
import zipfile
from pathlib import Path
import requests
import logging


logger = logging.getLogger(__name__)


GITHUB_REPO = "CogStack/cogstack-nlp"
SCRIPTS_PATH = "medcat-scripts/"
DOWNLOAD_URL_TEMPLATE = (
    f"https://api.github.com/repos/{GITHUB_REPO}/zipball/{{tag}}"
)


def _get_medcat_version() -> str:
    """Return the installed MedCAT version as 'major.minor'."""
    version = importlib.metadata.version("medcat")
    major, minor, *_ = version.split(".")
    return f"{major}.{minor}"


def _find_latest_scripts_tag(major_minor: str) -> str:
    """Query for the newest medcat-scripts tag matching 'v{major_minor}.*'."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
    tags = requests.get(url, timeout=15).json()

    matching = [
        t["name"]
        for t in tags
        if t["name"].startswith(f"medcat-scripts/v{major_minor}.")
        or t["name"].startswith(f"v{major_minor}.")
    ]
    if not matching:
        raise RuntimeError(
            f"No medcat-scripts tags found for MedCAT {major_minor}.x")

    # Tags are returned newest first by GitHub
    return matching[0]


def fetch_scripts(destination: str | Path = ".") -> Path:
    """Download the latest compatible medcat-scripts folder into.

    Args:
        destination (str | Path): The destination path. Defaults to ".".

    Returns:
        Path: The path of the scripts.
    """
    dest = Path(destination).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    version = _get_medcat_version()
    tag = _find_latest_scripts_tag(version)

    logger.info("Fetching scripts for MedCAT %s → tag %s}",
                version, tag)

    # Download the GitHub auto-generated zipball
    zip_url = DOWNLOAD_URL_TEMPLATE.format(tag=tag)
    with requests.get(zip_url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            for chunk in r.iter_content(chunk_size=8192):
                tmp.write(chunk)
            zip_path = Path(tmp.name)

    # Extract only medcat-scripts/ from the archive
    with zipfile.ZipFile(zip_path) as zf:
        for m in zf.namelist():
            if f"/{SCRIPTS_PATH}" not in m:
                continue
            # skip repo-hash prefix
            target = dest / Path(*Path(m).parts[2:])
            if m.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                with open(target, "wb") as f:
                    f.write(zf.read(m))

    logger.info("Scripts extracted to: %s", dest)
    return dest


def main(destination: str = ".",
         log_level: int | str = logging.INFO):
    logger.setLevel(log_level)
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
    fetch_scripts(destination)
