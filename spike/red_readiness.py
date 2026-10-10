"""Behavioral readiness RED: ignoring terminal job failures must fail by name."""

import json
import shutil
import tempfile
from pathlib import Path

from spike.red_proof import ROOT, execute


def main():
    with tempfile.TemporaryDirectory(prefix="2699-readiness-red-") as temp:
        root = Path(temp)
        for folder in ("spike", "tests"):
            shutil.copytree(
                ROOT / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        test = "tests/spike/test_readiness.py"
        green = execute(root, root / "green.xml", test)
        assert green[0] == 0 and not green[1] and not green[2]
        source = root / "spike/readiness.py"
        original = source.read_text()
        old = 'if any(counts[k] for k in ("failed", "dead_letter", "unknown")):'
        assert original.count(old) == 1
        # Return ready on these failures: do not merely fall through to a timeout.
        source.write_text(
            original.replace(old, old + "\n        return True\n    if False:")
        )
        shutil.rmtree(root / "spike/__pycache__", ignore_errors=True)
        code, failed, errors, passed = execute(root, root / "red.xml", test)
        expected = {
            f"test_failed_jobs_refuse_immediately[{s}]"
            for s in ("failed", "dead_letter", "unknown")
        }
        assert code == 1 and failed == expected and not errors, (code, failed, errors)
        assert "test_delayed_pending_drains_before_two_ready_observations" in passed
        assert "test_pending_timeout_never_launches" in passed
        print(
            json.dumps(
                {
                    "exit_code": code,
                    "failures": sorted(failed),
                    "controls": sorted(passed),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
