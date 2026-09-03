import asyncio
import collections
import json
import os
import signal
from collections.abc import AsyncIterator
from pathlib import Path

PASSTHROUGH_ENV_VARS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SHELL")
STDERR_TAIL_SIZE = 200


class ManagedProcess:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process
        self.stderr_tail: collections.deque[str] = collections.deque(maxlen=STDERR_TAIL_SIZE)
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    async def send_line(self, payload: dict) -> None:
        line = json.dumps(payload) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def close_stdin(self) -> None:
        if self._process.stdin and not self._process.stdin.is_closing():
            self._process.stdin.close()

    async def iter_stdout_lines(self) -> AsyncIterator[str]:
        async for raw_line in self._process.stdout:
            yield raw_line.decode(errors="replace")

    async def _drain_stderr(self) -> None:
        async for raw_line in self._process.stderr:
            self.stderr_tail.append(raw_line.decode(errors="replace"))

    async def wait(self) -> int:
        exit_code = await self._process.wait()
        await self._stderr_task
        return exit_code

    async def terminate(self, grace_period_seconds: float = 5.0) -> None:
        if self._process.returncode is not None:
            return
        signal_process_group(self._process.pid, signal.SIGTERM)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=grace_period_seconds)
        except TimeoutError:
            signal_process_group(self._process.pid, signal.SIGKILL)
            await self._process.wait()


def signal_process_group(pid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except ProcessLookupError:
        pass


async def spawn(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> ManagedProcess:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        env=build_subprocess_env(env),
        start_new_session=True,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return ManagedProcess(process)


def build_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The child can run arbitrary shell commands, so it gets an allow-listed env, never the backend's own (DB URLs, API keys, ...)."""
    env = {name: os.environ[name] for name in PASSTHROUGH_ENV_VARS if name in os.environ}
    env.update(extra or {})
    return env


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
