import asyncio
import json
import os
import signal
from collections.abc import AsyncIterator
from pathlib import Path


class ManagedProcess:
    def __init__(self, process: asyncio.subprocess.Process):
        self._process = process

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

    async def wait(self) -> int:
        return await self._process.wait()

    async def terminate(self, grace_period_seconds: float = 5.0) -> None:
        if self._process.returncode is not None:
            return
        self._process.send_signal(signal.SIGTERM)
        try:
            await asyncio.wait_for(self._process.wait(), timeout=grace_period_seconds)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()


async def spawn(command: list[str], cwd: Path) -> ManagedProcess:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return ManagedProcess(process)


def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
