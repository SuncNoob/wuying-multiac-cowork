from pathlib import Path
import subprocess

from cowork.store import Store


def git_init(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@cowork.local"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=root, check=True, capture_output=True)


def make_store(tmp_path: Path) -> Store:
    git_init(tmp_path)
    store = Store(tmp_path)
    store.ensure_layout()
    return store
