"""Design-loop agent (STOMPY-2800): a cheap local model drives a task.

Purpose: iterate on benchmark DESIGN (does the baseline saturate, does any
check need recalled state, is orientation measurable) without paying
provider rates. Output is tagged DESIGN and is never a verdict about Claude.

The model speaks Ollama's native chat API with tool calling. The sandbox is a
disposable container with /work mounted and no network. Memory tools in the
stompy arm are executed on the HOST through spike.mcp.MCP, so the container
never sees the fixture key.
"""

import hashlib
import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434"
OUTPUT_LIMIT = 12_000
RETRY_SECONDS = 15
MEMORY_TOOLS = {
    "stompy_recall_context": ("recall_context", ["topic"]),
    "stompy_context_search": ("context_search", ["query"]),
    "stompy_lock_context": ("lock_context", ["topic", "content"]),
    "stompy_ticket_search": ("ticket_search", ["query"]),
    "stompy_ticket": ("ticket", ["action", "title", "description", "ticket_id", "status"]),
}
SYSTEM = (
    "You are a software engineer working alone in /work, a frozen source tree. "
    "Use the tools to inspect and change files and run focused commands. "
    "Call done(summary) when the task is complete or you cannot proceed."
)


def _tool(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def tools(condition: str) -> list:
    schema = [
        _tool("bash", "Run a shell command in /work (no network).", {"cmd": {"type": "string"}}, ["cmd"]),
        _tool("read_file", "Read a file relative to /work.", {"path": {"type": "string"}}, ["path"]),
        _tool(
            "write_file",
            "Write a whole file relative to /work.",
            {"path": {"type": "string"}, "content": {"type": "string"}},
            ["path", "content"],
        ),
        _tool("done", "Finish with a short summary.", {"summary": {"type": "string"}}, ["summary"]),
    ]
    if condition == "stompy":
        schema += [
            _tool("stompy_recall_context", "Recall a memory context by topic.", {"topic": {"type": "string"}}, ["topic"]),
            _tool("stompy_context_search", "Search memory contexts.", {"query": {"type": "string"}}, ["query"]),
            _tool(
                "stompy_lock_context",
                "Store a decision or state as a memory context.",
                {"topic": {"type": "string"}, "content": {"type": "string"}},
                ["topic", "content"],
            ),
            _tool("stompy_ticket_search", "Search tickets.", {"query": {"type": "string"}}, ["query"]),
            _tool(
                "stompy_ticket",
                "Tickets: action list|get|create|append.",
                {
                    "action": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "ticket_id": {"type": "integer"},
                    "status": {"type": "string"},
                },
                ["action"],
            ),
        ]
    return schema


def confine(work: Path, relative: str) -> Path:
    target = (work / relative).resolve()
    if not target.is_relative_to(work.resolve()) or Path(relative).is_absolute():
        raise ValueError("path escapes /work: " + relative)
    return target


def memory_call(client, name: str, arguments: dict) -> str:
    if name not in MEMORY_TOOLS:
        raise ValueError("memory tool not allowlisted: " + name)
    tool, allowed = MEMORY_TOOLS[name]
    payload = {k: arguments[k] for k in allowed if k in arguments}
    if tool == "ticket" and payload.get("action") not in {"list", "get", "create", "append"}:
        raise ValueError("ticket action not allowlisted")
    payload["project"] = client.project  # the fixture project, never the model's choice
    return json.dumps(client.call(tool, payload, allow_error=True))[:OUTPUT_LIMIT]


class Sandbox:
    """Long-lived hardened container; commands run through docker exec."""

    def __init__(self, work: Path, image: str):
        self.name = "design2800-" + hashlib.sha256(str(work.resolve()).encode()).hexdigest()[:16]
        subprocess.run(
            [
                "docker", "run", "-d", "--name", self.name, "--init",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--memory", "4g", "--cpus", "2", "--pids-limit", "256",
                "--network", "none", "--read-only",
                "--tmpfs", "/tmp:rw,nosuid,size=256m",
                "-v", f"{work.resolve()}:/work", "--workdir", "/work",
                "--entrypoint", "sleep", image, "infinity",
            ],
            check=True, capture_output=True,
        )

    def exec(self, cmd: str, timeout: int):
        try:
            done = subprocess.run(
                ["docker", "exec", "-w", "/work", self.name, "bash", "-lc", cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            return done.returncode, done.stdout + done.stderr
        except subprocess.TimeoutExpired:
            return 124, f"command timed out after {timeout} s"

    def close(self):
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


def ollama_chat(model: str, base_url: str = OLLAMA, num_ctx: int = 32_768):
    def chat(messages, tool_schema):
        body = json.dumps(
            {"model": model, "messages": messages, "tools": tool_schema, "stream": False,
             "options": {"num_ctx": num_ctx, "temperature": 0.2}}
        ).encode()
        request = urllib.request.Request(
            base_url + "/api/chat", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=900) as response:
            return json.load(response)

    return chat


def dispatch(name, arguments, sandbox, work, memory, timeout):
    if name == "bash":
        code, out = sandbox.exec(str(arguments.get("cmd", "")), timeout)
        return f"exit {code}\n{out}"
    if name == "read_file":
        return confine(work, str(arguments.get("path", ""))).read_text(errors="replace")
    if name == "write_file":
        target = confine(work, str(arguments.get("path", "")))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(arguments.get("content", "")))
        return "written"
    if name in MEMORY_TOOLS:
        if memory is None:
            return "error: no memory service in this condition"
        return memory_call(memory, name, arguments)
    return "error: unknown tool " + name


def run_agent(chat, sandbox, work: Path, prompt: str, *, condition: str, memory, max_turns: int,
              timeout: int, log: Path, command_timeout: int = 300) -> list:
    schema = tools(condition)
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
    events = []
    started = time.monotonic()
    stop, summary = "max_turns", None
    with log.open("w") as stream:
        def emit(event):
            events.append(event)
            stream.write(json.dumps(event) + "\n")
            stream.flush()

        for turn in range(1, max_turns + 1):
            if time.monotonic() - started > timeout:
                stop = "timeout"
                break
            try:
                reply = chat(messages, schema)
            except (OSError, ValueError) as error:  # HTTPError/URLError are OSErrors
                # One retry covers a transient model-server error (seen as HTTP 500 between phases).
                emit({"type": "error", "turn": turn, "message": str(error)[:500]})
                time.sleep(RETRY_SECONDS)
                try:
                    reply = chat(messages, schema)
                except (OSError, ValueError) as again:
                    emit({"type": "error", "turn": turn, "message": str(again)[:500]})
                    stop = "chat_error"
                    break
            message = reply.get("message", {})
            calls = [
                {"id": c.get("id") or f"call-{turn}-{i}", "name": c["function"]["name"],
                 "arguments": c["function"].get("arguments") or {}}
                for i, c in enumerate(message.get("tool_calls") or [])
            ]
            emit({
                "type": "assistant", "turn": turn, "t": round(time.monotonic() - started, 3),
                "content": message.get("content", ""), "tool_calls": calls,
                "usage": {k: reply.get(k, 0) for k in ("prompt_eval_count", "eval_count")},
            })
            messages.append({"role": "assistant", "content": message.get("content", ""),
                             "tool_calls": message.get("tool_calls") or []})
            if not calls:
                stop = "no_tool_call"
                break
            finished = False
            for call in calls:
                if call["name"] == "done":
                    finished, summary = True, str(call["arguments"].get("summary", ""))
                    output = "acknowledged"
                else:
                    try:
                        output = dispatch(call["name"], call["arguments"], sandbox, work, memory, command_timeout)
                    except (ValueError, OSError) as error:
                        output = f"error: {error}"
                output = output[:OUTPUT_LIMIT]
                emit({"type": "tool_result", "id": call["id"], "name": call["name"], "output": output})
                messages.append({"role": "tool", "tool_name": call["name"], "content": output})
            if finished:
                stop = "done"
                break
        result = {"type": "result", "turns": sum(e["type"] == "assistant" for e in events), "stop_reason": stop}
        if summary is not None:
            result["summary"] = summary
        emit(result)
    return events


PRODUCTIVE_BASH = re.compile(r"\bpytest\b|python3? -m pytest|\bvitest\b|\bnpm test\b|\btsc\b")


def metrics(events: list) -> dict:
    hist, prompt_tokens, completion_tokens, turns = {}, 0, 0, 0
    orientation = None
    for event in events:
        if event.get("type") != "assistant":
            continue
        turns += 1
        usage = event.get("usage", {})
        prompt_tokens += usage.get("prompt_eval_count", 0)
        completion_tokens += usage.get("eval_count", 0)
        for call in event.get("tool_calls", []):
            hist[call["name"]] = hist.get(call["name"], 0) + 1
            productive = call["name"] == "write_file" or (
                call["name"] == "bash" and PRODUCTIVE_BASH.search(str(call["arguments"].get("cmd", "")))
            )
            if productive and orientation is None:
                # Orientation = launch up to and including the turn of the first productive act.
                orientation = {"turns": turns, "prompt_tokens": prompt_tokens, "seconds": event.get("t")}
    return {
        "turns": turns,
        "tokens": {"prompt": prompt_tokens, "completion": completion_tokens},
        "tool_histogram": dict(sorted(hist.items())),
        "memory_calls": sum(n for k, n in hist.items() if k in MEMORY_TOOLS),
        "orientation": orientation,
    }
