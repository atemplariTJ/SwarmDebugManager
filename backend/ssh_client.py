from __future__ import annotations

import asyncio
import socket
from collections.abc import Awaitable, Callable
from time import monotonic

import paramiko

from .settings import Settings

StreamCallback = Callable[[str, str], Awaitable[None]]


class SSHExecutionError(RuntimeError):
    pass


async def probe_tcp(host: str, port: int, timeout: float) -> int | None:
    started = monotonic()
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
    except (OSError, asyncio.TimeoutError):
        return None
    return int((monotonic() - started) * 1000)


async def check_ssh_login(host: str, port: int, settings: Settings) -> None:
    if not settings.ssh_configured:
        raise SSHExecutionError("ROBOT_SSH_USER and ROBOT_SSH_PASSWORD must be set")
    client: paramiko.SSHClient | None = None
    try:
        client = await asyncio.to_thread(_connect, host, port, settings)
    except (OSError, paramiko.SSHException, socket.timeout) as exc:
        raise SSHExecutionError(str(exc)) from exc
    finally:
        if client is not None:
            client.close()


def _connect(host: str, port: int, settings: Settings) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        port=port,
        username=settings.ssh_user,
        password=settings.ssh_password,
        timeout=settings.ssh_timeout_seconds,
        auth_timeout=settings.ssh_timeout_seconds,
        banner_timeout=settings.ssh_timeout_seconds,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


async def run_ssh_command(
    host: str,
    port: int,
    command: str,
    settings: Settings,
    emit: StreamCallback,
) -> int:
    if not settings.ssh_configured:
        raise SSHExecutionError("ROBOT_SSH_USER and ROBOT_SSH_PASSWORD must be set")
    if not command.strip():
        return 0

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, str | int | None]] = asyncio.Queue()

    def worker() -> None:
        client: paramiko.SSHClient | None = None
        try:
            client = _connect(host, port, settings)
            transport = client.get_transport()
            if transport is None:
                raise SSHExecutionError("SSH transport is unavailable")
            channel = transport.open_session()
            channel.get_pty(term="xterm")
            channel.exec_command(command)
            channel.settimeout(0.2)

            while True:
                if channel.recv_ready():
                    data = channel.recv(4096).decode("utf-8", errors="replace")
                    loop.call_soon_threadsafe(queue.put_nowait, ("stdout", data))
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096).decode("utf-8", errors="replace")
                    loop.call_soon_threadsafe(queue.put_nowait, ("stderr", data))
                if channel.exit_status_ready():
                    while channel.recv_ready():
                        data = channel.recv(4096).decode("utf-8", errors="replace")
                        loop.call_soon_threadsafe(queue.put_nowait, ("stdout", data))
                    while channel.recv_stderr_ready():
                        data = channel.recv_stderr(4096).decode("utf-8", errors="replace")
                        loop.call_soon_threadsafe(queue.put_nowait, ("stderr", data))
                    code = channel.recv_exit_status()
                    loop.call_soon_threadsafe(queue.put_nowait, ("exit", code))
                    break
        except (OSError, paramiko.SSHException, socket.timeout, SSHExecutionError) as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            if client is not None:
                client.close()
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    task = asyncio.create_task(asyncio.to_thread(worker))
    exit_code = 1
    try:
        while True:
            kind, payload = await asyncio.wait_for(
                queue.get(),
                timeout=settings.command_timeout_seconds,
            )
            if kind in {"stdout", "stderr", "error"}:
                await emit(kind, str(payload))
            elif kind == "exit":
                exit_code = int(payload)
            elif kind == "done":
                break
    except asyncio.TimeoutError as exc:
        await emit("error", f"command timed out after {settings.command_timeout_seconds}s")
        raise SSHExecutionError("command timed out") from exc
    finally:
        await task

    return exit_code
