#!/usr/bin/env python3
"""Phase 0.2: the process RuntimeService actually spawns, standing in for `claude`. It outlives the backend, so exit status, output and process identity become durable facts on disk instead of only living in a parent that can die."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from process import read_process_start_time

# allow-comment: codex P1 -- stdout/stderr can carry source code, tool output or secrets, same sensitivity as mcp.json (which already gets 0600); unlike mcp.json these persist after the run, so a shared host's default umask must never leave them group/world-readable.
RUN_DIR_MODE = 0o700
RUN_FILE_MODE = 0o600


async def main() -> int:
    run_directory, cwd, command = parse_args()
    run_directory.mkdir(parents=True, exist_ok=True)
    os.chmod(run_directory, RUN_DIR_MODE)
    child = await spawn_child(command, cwd)
    write_proc_file(run_directory, child, command)
    await drain_until_exit(child, run_directory)
    exit_code = await child.wait()
    write_exit_file(run_directory, exit_code)
    return exit_code


def parse_args() -> tuple[Path, Path, list[str]]:
    return Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]


async def spawn_child(command: list[str], cwd: Path) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        *command, cwd=str(cwd),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )


def write_proc_file(run_directory: Path, child: asyncio.subprocess.Process, command: list[str]) -> None:
    payload = {"pid": child.pid, "start_time": read_process_start_time(child.pid), "argv": command}
    atomic_write_json(run_directory / "proc.json", payload)


def write_exit_file(run_directory: Path, exit_code: int) -> None:
    atomic_write_json(run_directory / "exit.json", {"exit_code": exit_code, "ended_at": time.time()})


def atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload))
    os.chmod(tmp_path, RUN_FILE_MODE)
    tmp_path.replace(path)


async def drain_until_exit(child: asyncio.subprocess.Process, run_directory: Path) -> None:
    relay_task = asyncio.create_task(relay_stdin(child))
    await asyncio.gather(
        tee_stdout(child, run_directory / "stdout.jsonl"),
        drain_to_file(child.stderr, run_directory / "stderr.log"),
    )
    relay_task.cancel()


async def relay_stdin(child: asyncio.subprocess.Process) -> None:
    """The backend's own stdin to this script mirrors straight through to claude: a one-shot task run closes it right after the first message, same as before; a meeting session keeps writing turns for as long as it stays connected."""
    reader = await open_stdin_reader()
    async for line in reader:
        child.stdin.write(line)
        await child.stdin.drain()
    close_child_stdin(child)


async def open_stdin_reader() -> asyncio.StreamReader:
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    return reader


def close_child_stdin(child: asyncio.subprocess.Process) -> None:
    if child.stdin and not child.stdin.is_closing():
        child.stdin.close()


async def tee_stdout(child: asyncio.subprocess.Process, stdout_path: Path) -> None:
    """Mirrors claude's stdout to this script's own stdout (so a live OwnedProcess can read it directly, same as before) while also appending it to disk (so an AdoptedProcess can follow it after a restart)."""
    with open_private(stdout_path) as sink:
        async for raw_line in child.stdout:
            sys.stdout.buffer.write(raw_line)
            sys.stdout.buffer.flush()
            sink.write(raw_line)
            sink.flush()


async def drain_to_file(stream: asyncio.StreamReader, path: Path) -> None:
    with open_private(path) as sink:
        async for raw_line in stream:
            sink.write(raw_line)
            sink.flush()


def open_private(path: Path):
    handle = path.open("ab")
    os.chmod(path, RUN_FILE_MODE)
    return handle


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
