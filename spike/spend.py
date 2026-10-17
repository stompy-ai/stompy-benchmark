"""Cross-attempt local spike ceiling. Unknown attempts keep their reservation."""

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

# Durable: the previous /private/tmp ledger was reaped by the system temp
# cleaner on 2026-10-16, which would have silently restored a fresh $30.
LEDGER = Path.home() / ".config" / "stompy" / "benchmark-spend.json"
CEILING = 30.0  # Markus, STOMPY-2744, 2026-10-11; prior attempts stay charged.


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        # A missing, empty or corrupt ledger is an error, never a fresh budget.
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; seed it with spend.seed")
        data = json.loads(path.read_text())
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


def seed(path, identity, amount):
    """One-time creation of a ledger carrying a known historical upper bound."""
    if path.exists():
        raise FileExistsError(f"{path} exists; never reseed a ledger")
    if amount < 0 or amount > CEILING:
        raise ValueError("invalid historical upper bound")
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"upper_bound_usd": amount, "state": "settled_upper_bound"}
    path.write_text(json.dumps({identity: row}))
