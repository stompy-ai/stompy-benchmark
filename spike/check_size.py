"""Spike modules pay the final 500-line rung without changing any baseline."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = [*root.glob("spike/*.py"), *root.glob("tasks/lifecycle-rest/**/*.py")]
oversize = [
    str(p.relative_to(root)) for p in files if len(p.read_text().splitlines()) > 500
]
if oversize:
    raise SystemExit("oversize: " + ", ".join(oversize))
print(f"{len(files)} spike/task modules <=500 lines; no baseline changed")
