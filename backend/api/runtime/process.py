import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncIterator
from pathlib import Path

PASSTHROUGH_ENV_VARS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SHELL")
STDERR_TAIL_SIZE = 200
FOLLOW_POLL_SECONDS = 0.3
SUPERVISOR_SCRIPT = Path(__file__).with_name("supervisor.py")


def run_dir(runtime_root: Path, agent_id, run_id) -> Path:
    return runtime_root / str(agent_id) / str(run_id)


class OwnedProcess:
    """This backend forked it (Phase 0.3): has the live asyncio handle, so it can wait() and write stdin."""

    def __init__(self, process: asyncio.subprocess.Process, run_directory: Path):
        self._process = process
        self.run_directory = run_directory

    @property
    def pid(self) -> int:
        return self._process.pid

    async def send_line(self, payload: dict) -> None:
        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def close_stdin(self) -> None:
        if self._process.stdin and not self._process.stdin.is_closing():
            self._process.stdin.close()

    async def iter_stdout_lines(self, from_offset: int = 0) -> AsyncIterator[tuple[str, int]]:
        """Reads the supervisor's own (teed) stdout live, tracking the same byte offset the file on disk is accumulating, so a crash mid-run resumes an AdoptedProcess from exactly this point."""
        offset = from_offset
        async for raw_line in self._process.stdout:
            offset += len(raw_line)
            yield raw_line.decode(errors="replace"), offset

    async def wait(self) -> int:
        return await self._process.wait()

    async def terminate(self, grace_period_seconds: float = 5.0) -> None:
        await terminate_pid(self.pid, grace_period_seconds)

    @property
    def stderr_tail(self) -> list[str]:
        return read_stderr_tail(self.run_directory)


class AdoptedProcess:
    """Reattached after a restart (Phase 0.3): no asyncio handle survives a crash, so liveness, exit status and output all come from files a supervisor process wrote independently of this backend."""

    def __init__(self, run_directory: Path):
        self.run_directory = run_directory

    @property
    def pid(self) -> int | None:
        return read_proc_file(self.run_directory).get("pid")

    async def send_line(self, payload: dict) -> None:
        raise RuntimeError("an adopted run has no stdin: its owning backend process is gone")

    async def close_stdin(self) -> None:
        return None

    async def iter_stdout_lines(self, from_offset: int = 0) -> AsyncIterator[tuple[str, int]]:
        offset = from_offset
        while True:
            new_lines, offset = read_new_lines(self.run_directory / "stdout.jsonl", offset)
            for line in new_lines:
                yield line, offset
            if new_lines:
                continue
            if self.is_finished():
                return
            await asyncio.sleep(FOLLOW_POLL_SECONDS)

    async def wait(self) -> int | None:
        while not self.is_finished():
            await asyncio.sleep(FOLLOW_POLL_SECONDS)
        return read_exit_file(self.run_directory).get("exit_code")

    async def terminate(self, grace_period_seconds: float = 5.0) -> None:
        if self.pid is not None:
            await terminate_pid(self.pid, grace_period_seconds)

    def is_finished(self) -> bool:
        if (self.run_directory / "exit.json").exists():
            return True
        return not self.is_alive()

    def is_alive(self) -> bool:
        return is_run_identity_alive(self.run_directory)

    @property
    def stderr_tail(self) -> list[str]:
        return read_stderr_tail(self.run_directory)


def is_run_identity_alive(run_directory: Path) -> bool:
    """A bare is_pid_alive(pid) accepts any process now holding that number; comparing the recorded /proc start time catches pid reuse after the original process is long gone."""
    proc = read_proc_file(run_directory)
    pid = proc.get("pid")
    if pid is None or not is_pid_alive(pid):
        return False
    recorded_start = proc.get("start_time")
    return recorded_start is None or recorded_start == read_process_start_time(pid)


def read_proc_file(run_directory: Path) -> dict:
    return read_json_file(run_directory / "proc.json")


def read_exit_file(run_directory: Path) -> dict:
    return read_json_file(run_directory / "exit.json")


def read_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_stderr_tail(run_directory: Path, max_lines: int = STDERR_TAIL_SIZE) -> list[str]:
    try:
        lines = (run_directory / "stderr.log").read_text(errors="replace").splitlines()
    except FileNotFoundError:
        return []
    return lines[-max_lines:]


def read_new_lines(path: Path, offset: int) -> tuple[list[str], int]:
    chunk = read_bytes_from(path, offset)
    if chunk is None:
        return [], offset
    return parse_complete_lines(chunk, offset)


def read_bytes_from(path: Path, offset: int) -> bytes | None:
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            return handle.read()
    except FileNotFoundError:
        return None


def parse_complete_lines(chunk: bytes, offset: int) -> tuple[list[str], int]:
    """Only complete lines advance the offset: a partial trailing line means the writer is mid-flush, and yielding it would hand a caller a line it must not treat as a real event."""
    lines = []
    for raw_line in chunk.splitlines(keepends=True):
        if not raw_line.endswith(b"\n"):
            break
        offset += len(raw_line)
        lines.append(raw_line.decode(errors="replace"))
    return lines, offset


async def spawn(command: list[str], cwd: Path, run_directory: Path, env: dict[str, str] | None = None) -> OwnedProcess:
    """Spawns runtime/supervisor.py as the child instead of the target command directly (Phase 0.2): the supervisor outlives this backend and makes exit status, output and identity durable facts on disk."""
    supervisor_command = [sys.executable, str(SUPERVISOR_SCRIPT), str(run_directory), str(cwd), *command]
    process = await asyncio.create_subprocess_exec(
        *supervisor_command,
        env=build_subprocess_env(env),
        start_new_session=True,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    return OwnedProcess(process, run_directory)


def build_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The child can run arbitrary shell commands, so it gets an allow-listed env, never the backend's own (DB URLs, API keys, ...)."""
    env = {name: os.environ[name] for name in PASSTHROUGH_ENV_VARS if name in os.environ}
    env.update(extra or {})
    return env


async def terminate_pid(pid: int, grace_period_seconds: float = 5.0) -> None:
    """No ManagedProcess to await for an adopted run, or one this process didn't spawn directly (e.g. session rotation): poll instead of wait()."""
    if not is_pid_alive(pid):
        return
    signal_process_group(pid, signal.SIGTERM)
    if await wait_for_pid_exit(pid, grace_period_seconds):
        return
    signal_process_group(pid, signal.SIGKILL)
    await wait_for_pid_exit(pid, grace_period_seconds)


async def wait_for_pid_exit(pid: int, timeout_seconds: float, poll_interval_seconds: float = 0.2) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        if not is_pid_alive(pid):
            return True
        await asyncio.sleep(poll_interval_seconds)
    return not is_pid_alive(pid)


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_process_start_time(pid: int) -> str | None:
    """Linux-only identity fingerprint (field 22 of /proc/<pid>/stat, in clock ticks since boot): absent elsewhere, in which case identity falls back to the pid alone."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except FileNotFoundError:
        return None
    return stat.rsplit(")", 1)[-1].split()[19]


def signal_process_group(pid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except ProcessLookupError:
        pass
