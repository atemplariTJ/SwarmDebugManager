from __future__ import annotations

import asyncio
import ipaddress
from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class DiscoveredRobot:
    id: str
    host: str
    port: int
    status: str
    latency_ms: int


async def _probe(host: str, port: int, timeout: float) -> int | None:
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


async def scan_ssh_hosts(
    cidr: str,
    port: int,
    timeout: float,
    concurrency: int,
) -> list[DiscoveredRobot]:
    network = ipaddress.ip_network(cidr, strict=False)
    semaphore = asyncio.Semaphore(concurrency)
    results: list[DiscoveredRobot] = []

    async def scan_one(ip: ipaddress._BaseAddress) -> None:
        host = str(ip)
        async with semaphore:
            latency_ms = await _probe(host, port, timeout)
        if latency_ms is not None:
            suffix = host.split(".")[-1] if "." in host else host.replace(":", "")
            results.append(
                DiscoveredRobot(
                    id=f"R{suffix}",
                    host=host,
                    port=port,
                    status="ssh-open",
                    latency_ms=latency_ms,
                )
            )

    await asyncio.gather(*(scan_one(ip) for ip in network.hosts()))
    return sorted(results, key=lambda item: tuple(int(p) for p in item.host.split(".") if p.isdigit()))
