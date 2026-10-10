#!/usr/bin/env bash
# Only this model-call process reads the authorized vault credential.
set -euo pipefail
set +x
source "$HOME/.config/stompy/op.env"
provider_key="$(op read op://Stompy/stompy-prod/ANTHROPIC_API_KEY_STOMPY_BENCHMARK 2>/dev/null)"
if [[ -z "$provider_key" ]]; then exit 1; fi
# Value travels only over stdin, never Docker Config.Env, argv or an env file.
printf '%s\n' "$provider_key" | docker run --rm -i --name "$1" \
  --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 256m --pids-limit 64 --tmpfs /tmp:rw,nosuid,size=16m \
  -e "BENCH_GATEWAY_BUDGET=$4" -e "BENCH_GATEWAY_TOKENS=$5" \
  -v "$2:/gateway:ro" -v "$3:/evidence" \
  --workdir /gateway --entrypoint python "$6" gateway_server.py
