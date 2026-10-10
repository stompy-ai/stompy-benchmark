"""Frozen source export; agent gets no Git history or operator configuration."""

import io
import shutil
import subprocess
import tarfile
from pathlib import Path

SHA = "c40570b266df628ed1f5a9260ba77096d8bfe71a"


def snapshot(repository: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    archive = subprocess.check_output(["git", "-C", str(repository), "archive", SHA])
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(destination, filter="data")
    for path in sorted(
        destination.rglob("*"), key=lambda p: len(p.parts), reverse=True
    ):
        if path.name.startswith(".env") or path.name in {
            ".git",
            ".claude",
            ".codex",
            ".agents",
        }:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    if any(
        p.name == ".git" or p.name.startswith(".env") for p in destination.rglob("*")
    ):
        raise ValueError("snapshot retained forbidden state")
