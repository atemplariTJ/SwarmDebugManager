import asyncio

import pytest

from backend.discovery import scan_ssh_hosts


@pytest.mark.asyncio
async def test_scan_ssh_hosts_finds_open_port():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        robots = await scan_ssh_hosts("127.0.0.1/32", port, timeout=1, concurrency=4)
    finally:
        server.close()
        await server.wait_closed()

    assert len(robots) == 1
    assert robots[0].host == "127.0.0.1"
    assert robots[0].port == port
    assert robots[0].status == "ssh-open"


@pytest.mark.asyncio
async def test_scan_ssh_hosts_ignores_closed_port():
    robots = await scan_ssh_hosts("127.0.0.1/32", 9, timeout=0.1, concurrency=4)

    assert robots == []
