import sys
from pathlib import Path


def project_root() -> Path:
    """Return the project/runtime root for user-visible files."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    return Path(__file__).resolve().parent.parent.parent


def resource_path(*parts) -> Path:
    """Return a bundled resource path, compatible with PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", project_root()))
    return base.joinpath(*parts)
