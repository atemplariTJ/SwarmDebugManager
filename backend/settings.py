from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    scan_cidr: str = "10.42.0.0/24"
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_password: str = ""
    ssh_timeout_seconds: float = 3.0
    command_timeout_seconds: float = 60.0
    max_scan_concurrency: int = 128

    @property
    def ssh_configured(self) -> bool:
        return bool(self.ssh_user and self.ssh_password)


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        scan_cidr=os.getenv("ROBOT_SCAN_CIDR", "10.42.0.0/24"),
        ssh_port=int(os.getenv("ROBOT_SSH_PORT", "22")),
        ssh_user=os.getenv("ROBOT_SSH_USER", ""),
        ssh_password=os.getenv("ROBOT_SSH_PASSWORD", ""),
        ssh_timeout_seconds=float(os.getenv("ROBOT_SSH_TIMEOUT_SECONDS", "3")),
        command_timeout_seconds=float(os.getenv("ROBOT_COMMAND_TIMEOUT_SECONDS", "60")),
        max_scan_concurrency=int(os.getenv("ROBOT_SCAN_CONCURRENCY", "128")),
    )
