"""Cross-attempt local spike ceiling. Unknown attempts keep their reservation."""

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

LEDGER = Path("/private/tmp/stompy-2699-spend.json")
CEILING = 25.0  # Markus, STOMPY-2699, 2026-10-11; prior attempts stay charged.


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        # An existing empty/corrupt ledger is an error, never a fresh budget.
        data = json.loads(path.read_text()) if path.exists() else {}
        yield data
        temporary = path.with_suffix(".tmp")
        with temporary.open("w") as writer:
            json.dump(data, writer)
            writer.flush()
            os.fsync(writer.fileno())
        temporary.replace(path)
        fcntl.flock(handle, fcntl.LOCK_UN)


def reserve(identity, amount, path=LEDGER):
    if amount <= 0 or amount > 4.5:
        raise ValueError("invalid cell reservation")
    with locked(path) as data:
        if identity in data:
            raise ValueError("attempt already reserved; never reuse an identity")
        if (
            sum(row["upper_bound_usd"] for row in data.values()) + amount
            > CEILING + 1e-9
        ):
            raise ValueError(
                f"spike ${CEILING:g} ceiling would be exceeded; ask Markus"
            )
        data[identity] = {"upper_bound_usd": amount, "state": "reserved"}


def settle(identity, evidence, path=LEDGER):
    if evidence.get("billing_unknown"):
        return
    with locked(path) as data:
        amount = evidence["charged_upper_bound_usd"]
        if not 0 <= amount <= data[identity]["upper_bound_usd"]:
            raise ValueError("invalid spend settlement")
        data[identity] = {"upper_bound_usd": amount, "state": "settled_upper_bound"}
