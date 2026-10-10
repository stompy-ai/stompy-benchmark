"""Inside the agent container: allowlist process env, then exec the provider CLI."""

import json
import os
import sys
from pathlib import Path

from benchmark_integrity import clean_environment

env = clean_environment(os.environ)
env.update(
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
    PYTHONDONTWRITEBYTECODE="1",
    ENABLE_TOOL_SEARCH="false",
)
for key in (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
):
    if os.environ.get(key):
        env[key] = os.environ[key]
if env.get("ANTHROPIC_BASE_URL") != "http://127.0.0.1:18777":
    raise SystemExit("Private loopback gateway missing")
Path("/home/benchmark/launch-env-keys.json").write_text(json.dumps(sorted(env)))
os.execve("/usr/local/bin/claude", ["claude", *sys.argv[1:]], env)
