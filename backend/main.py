from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .discovery import DiscoveredRobot, scan_ssh_hosts
from .fleet import build_fleet, robot_payload
from .settings import get_settings
from .ssh_client import SSHExecutionError, check_ssh_login, probe_tcp, run_ssh_command

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
LEGACY_HTML = FRONTEND_DIR / "MGS Debug Console.html"

app = FastAPI(title="Swarm Debug Manager")
robots_cache: dict[str, DiscoveredRobot] = {}
robot_status_cache: dict[str, dict[str, object]] = {}

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
        "robot_count": len(robot_status_cache),
    }


@app.get("/api/fleet")
async def fleet(subnet: str | None = None, offset: int = 0, count: int = 30) -> dict[str, Any]:
    settings = get_settings()
    robots = build_fleet(
        subnet=subnet or settings.scan_cidr.rsplit(".", 1)[0],
        offset=offset,
        count=max(1, min(count, 200)),
        port=settings.ssh_port,
        statuses=robot_status_cache,
    )
    return {"robots": [robot_payload(robot) for robot in robots]}


@app.post("/api/robots/{robot_id}/connect")
async def connect_robot(robot_id: str, body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    ip = str(body.get("ip") or body.get("host") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    port = int(body.get("port") or settings.ssh_port)
    try:
        await check_ssh_login(ip, port, settings)
    except SSHExecutionError as exc:
        robot_status_cache[robot_id] = {
            "status": "error",
            "state": "error",
            "ping": None,
            "batt": 0,
            "errCount": 1,
            "ip": ip,
            "port": port,
        }
        return {"id": robot_id, **robot_status_cache[robot_id], "message": str(exc)}

    robot_status_cache[robot_id] = {
        "status": "online",
        "state": "idle",
        "ping": None,
        "batt": 55,
        "errCount": 0,
        "ip": ip,
        "port": port,
    }
    return {"id": robot_id, **robot_status_cache[robot_id]}


@app.post("/api/robots/{robot_id}/disconnect")
async def disconnect_robot(robot_id: str) -> dict[str, Any]:
    cached = robot_status_cache.get(robot_id, {})
    robot_status_cache[robot_id] = {
        **cached,
        "status": "offline",
        "state": "idle",
        "ping": None,
        "batt": 0,
        "errCount": 0,
    }
    return {"id": robot_id, **robot_status_cache[robot_id]}


@app.post("/api/robots/{robot_id}/ping")
async def ping_robot(robot_id: str, body: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    ip = str(body.get("ip") or body.get("host") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="ip is required")
    port = int(body.get("port") or settings.ssh_port)
    latency_ms = await probe_tcp(ip, port, settings.ssh_timeout_seconds)
    cached = robot_status_cache.get(robot_id, {})
    status = "online" if latency_ms is not None and cached.get("status") != "error" else cached.get("status", "offline")
    robot_status_cache[robot_id] = {
        **cached,
        "status": status,
        "ping": latency_ms,
        "ip": ip,
        "port": port,
    }
    return {"id": robot_id, "ip": ip, "port": port, "ping": latency_ms, "status": status}


@app.post("/api/robots/broadcast")
async def broadcast(body: dict[str, Any]) -> dict[str, Any]:
    command_name = str(body.get("command", "")).strip().lower()
    targets = body.get("targets") or []
    if command_name not in {"stop", "restart"}:
        raise HTTPException(status_code=400, detail="unsupported broadcast command")
    shell_command = "stop" if command_name == "stop" else "reboot"
    settings = get_settings()
    results: list[dict[str, Any]] = []
    for target in targets:
        robot_id = str(target.get("id", "")).strip()
        ip = str(target.get("ip", "")).strip()
        if not robot_id or not ip:
            continue
        chunks: list[dict[str, str]] = []

        async def emit(kind: str, data: str) -> None:
            chunks.append({"type": kind, "data": data})

        try:
            code = await run_ssh_command(ip, int(target.get("port") or settings.ssh_port), shell_command, settings, emit)
            results.append({"id": robot_id, "exit_code": code, "chunks": chunks})
        except SSHExecutionError as exc:
            results.append({"id": robot_id, "exit_code": 1, "chunks": [{"type": "error", "data": str(exc)}]})
    return {"results": results}


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


@app.websocket("/ws/robots/{robot_id}/terminal")
async def robot_terminal(websocket: WebSocket, robot_id: str) -> None:
    await websocket.accept()
    settings = get_settings()
    ip = websocket.query_params.get("ip", "")
    if not ip:
        await websocket.send_json({"type": "error", "data": "ip query parameter is required"})
        await websocket.close()
        return
    port = int(websocket.query_params.get("port", str(settings.ssh_port)))

    async def emit(kind: str, data: str) -> None:
        await websocket.send_json({"type": kind, "data": data})

    try:
        while True:
            message = await websocket.receive_json()
            command = str(message.get("command", "")).strip()
            if not command:
                continue
            await websocket.send_json({"type": "cmd", "data": command})
            try:
                code = await run_ssh_command(ip, port, command, settings, emit)
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
