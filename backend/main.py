from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .discovery import DiscoveredRobot, scan_ssh_hosts
from .settings import get_settings
from .ssh_client import SSHExecutionError, run_ssh_command

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
LEGACY_HTML = FRONTEND_DIR / "MGS Debug Console.html"

app = FastAPI(title="Swarm Debug Manager")
robots_cache: dict[str, DiscoveredRobot] = {}

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _robot_payload(robot: DiscoveredRobot) -> dict[str, Any]:
    return {
        "id": robot.id,
        "host": robot.host,
        "port": robot.port,
        "status": robot.status,
        "latency_ms": robot.latency_ms,
    }


@app.get("/")
async def index() -> FileResponse:
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return FileResponse(LEGACY_HTML)


@app.get("/legacy")
async def legacy() -> FileResponse:
    return FileResponse(LEGACY_HTML)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "scan_cidr": settings.scan_cidr,
        "ssh_port": settings.ssh_port,
        "ssh_configured": settings.ssh_configured,
        "robot_count": len(robots_cache),
    }


@app.post("/api/robots/scan")
async def scan_robots() -> dict[str, Any]:
    settings = get_settings()
    robots = await scan_ssh_hosts(
        cidr=settings.scan_cidr,
        port=settings.ssh_port,
        timeout=settings.ssh_timeout_seconds,
        concurrency=settings.max_scan_concurrency,
    )
    robots_cache.clear()
    robots_cache.update({robot.host: robot for robot in robots})
    return {"robots": [_robot_payload(robot) for robot in robots]}


@app.get("/api/robots")
async def list_robots() -> dict[str, Any]:
    return {"robots": [_robot_payload(robot) for robot in robots_cache.values()]}


@app.websocket("/ws/terminal/{robot_host}")
async def terminal(websocket: WebSocket, robot_host: str) -> None:
    await websocket.accept()
    settings = get_settings()
    port = settings.ssh_port
    if robot_host in robots_cache:
        port = robots_cache[robot_host].port

    async def emit(kind: str, data: str) -> None:
        await websocket.send_json({"type": kind, "data": data})

    try:
        while True:
            message = await websocket.receive_json()
            command = str(message.get("command", "")).strip()
            if not command:
                continue
            await websocket.send_json({"type": "command", "data": command})
            try:
                code = await run_ssh_command(robot_host, port, command, settings, emit)
                await websocket.send_json({"type": "exit", "code": code})
            except SSHExecutionError as exc:
                await websocket.send_json({"type": "error", "data": str(exc)})
    except WebSocketDisconnect:
        return


@app.post("/api/robots/{robot_host}/command")
async def run_command_once(robot_host: str, body: dict[str, Any]) -> dict[str, Any]:
    command = str(body.get("command", "")).strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")

    chunks: list[dict[str, str]] = []

    async def emit(kind: str, data: str) -> None:
        chunks.append({"type": kind, "data": data})

    settings = get_settings()
    port = robots_cache.get(robot_host).port if robot_host in robots_cache else settings.ssh_port
    code = await run_ssh_command(robot_host, port, command, settings, emit)
    return {"exit_code": code, "chunks": chunks}
