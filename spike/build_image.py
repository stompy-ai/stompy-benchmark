"""Build the agent runtime from locally verified base images."""

import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
for image, digest in json.loads((root / "images.json").read_text()).items():
    actual = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
    ).strip()
    if actual != digest:
        raise SystemExit(f"Base image drift: {image}")
subprocess.run(
    [
        "docker",
        "build",
        "--pull=false",
        "-f",
        str(root / "Dockerfile.agent"),
        "-t",
        "stompy-2699-agent:spike",
        str(root),
    ],
    check=True,
)
print(
    subprocess.check_output(
        [
            "docker",
            "image",
            "inspect",
            "stompy-2699-agent:spike",
            "--format",
            "{{.Id}}",
        ],
        text=True,
    ).strip()
)
