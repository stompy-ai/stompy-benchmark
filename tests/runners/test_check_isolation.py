import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "..", "runners", "check-isolation.py")
spec = importlib.util.spec_from_file_location("check_isolation", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def stream(servers):
    return json.dumps({"type": "system", "subtype": "init", "mcp_servers": servers}) + "\n"


class VerdictTests(unittest.TestCase):
    def test_nomemory_with_no_servers_is_isolated(self):
        self.assertTrue(mod.verdict("nomemory", [])["ok"])

    def test_nomemory_with_operator_stompy_connector_is_violated(self):
        v = mod.verdict("nomemory", [{"name": "stompy-direct", "status": "connected"}])
        self.assertFalse(v["ok"])

    def test_stompy_with_only_injected_server_is_isolated(self):
        self.assertTrue(mod.verdict("stompy", [{"name": "stompy", "status": "connected"}])["ok"])

    def test_stompy_with_operator_servers_beside_it_is_violated(self):
        servers = [{"name": "stompy", "status": "connected"}, {"name": "claude.ai Stompy", "status": "connected"}]
        self.assertFalse(mod.verdict("stompy", servers)["ok"])

    def test_stompy_server_that_failed_to_connect_is_violated(self):
        self.assertFalse(mod.verdict("stompy", [{"name": "stompy", "status": "failed"}])["ok"])

    def test_missing_init_event_is_not_a_pass(self):
        self.assertFalse(mod.verdict("nomemory", None)["ok"])


class CliTests(unittest.TestCase):
    def run_cli(self, condition, body):
        with tempfile.NamedTemporaryFile("w", suffix=".ndjson", delete=False) as f:
            f.write(body)
        try:
            return subprocess.run([sys.executable, SCRIPT, condition, f.name], capture_output=True).returncode
        finally:
            os.unlink(f.name)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("nomemory", stream([])), 0)
        self.assertEqual(self.run_cli("nomemory", stream([{"name": "x", "status": "connected"}])), 1)
        self.assertEqual(self.run_cli("nomemory", "not json\n"), 1)


if __name__ == "__main__":
    unittest.main()
