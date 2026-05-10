from pathlib import Path

from geekclock.system.resources import project_root, resource_path


def test_project_root_is_directory():
    root = project_root()
    assert root.is_dir()
    assert (root / "main.py").exists() or (root / "geekclock").is_dir()


def test_resource_path_returns_absolute():
    p = resource_path("sounds")
    assert Path(p).is_absolute()


def test_resource_path_relative_input():
    p = str(resource_path("sounds/bell1.mp3"))
    assert p.endswith("bell1.mp3") or ("sounds" in p)
