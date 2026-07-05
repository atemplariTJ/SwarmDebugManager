from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FleetRobot:
    id: str
    id_num: int
    ip: str
    port: int
    status: str
    state: str
    ping: int | None
    batt: int
    err_count: int


def make_robot_ip(subnet: str, id_num: int, offset: int) -> str:
    clean = subnet.strip().rstrip(".")
    return f"{clean}.{id_num + offset}"


def build_fleet(
    subnet: str,
    offset: int,
    count: int,
    port: int,
    statuses: dict[str, dict[str, object]] | None = None,
) -> list[FleetRobot]:
    statuses = statuses or {}
    robots: list[FleetRobot] = []
    for id_num in range(1, count + 1):
        robot_id = f"R{id_num:02d}"
        ip = make_robot_ip(subnet, id_num, offset)
        cached = statuses.get(robot_id, {})
        status = str(cached.get("status", "offline"))
        robots.append(
            FleetRobot(
                id=robot_id,
                id_num=id_num,
                ip=ip,
                port=port,
                status=status,
                state=str(cached.get("state", "idle" if status != "error" else "error")),
                ping=cached.get("ping") if isinstance(cached.get("ping"), int) else None,
                batt=int(cached.get("batt", 0 if status == "offline" else 55)),
                err_count=int(cached.get("errCount", 1 if status == "error" else 0)),
            )
        )
    return robots


def robot_payload(robot: FleetRobot) -> dict[str, object]:
    return {
        "id": robot.id,
        "idNum": robot.id_num,
        "ip": robot.ip,
        "host": robot.ip,
        "port": robot.port,
        "status": robot.status,
        "state": robot.state,
        "ping": robot.ping,
        "pinging": False,
        "batt": robot.batt,
        "errCount": robot.err_count,
    }
