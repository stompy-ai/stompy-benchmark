"""Inside the agent container: allowlist process env, then exec the provider CLI."""

import json
import os
import sys
from pathlib import Path

from benchmark_integrity import clean_environment

env = clean_environment(os.environ)
env.update(CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1", PYTHONDONTWRITEBYTECODE="1")
for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
    if os.environ.get(key):
        env[key] = os.environ[key]
if not any(key in env for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")):
    raise SystemExit("Provider authentication missing")
Path("/home/benchmark/launch-env-keys.json").write_text(json.dumps(sorted(env)))
os.execve("/usr/local/bin/claude", ["claude", *sys.argv[1:]], env)
