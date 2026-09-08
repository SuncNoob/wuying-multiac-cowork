"""Laptop-side local config. Never committed; holds SSH and GitHub secrets."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cowork.sshutil import SSHTarget

DEFAULT_PATH = Path.home() / ".config" / "cowork" / "config.json"
REPO_LOCAL_PATH = Path("cowork.local.json")


def config_path() -> Path:
    env = os.environ.get("COWORK_CONFIG")
    if env:
        return Path(env)
    if REPO_LOCAL_PATH.exists():
        return REPO_LOCAL_PATH
    return DEFAULT_PATH


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or config_path()
    if not p.exists():
        return {"github": {}, "ssh": {}, "agents": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p.chmod(0o600)
    return p


def password_from(data: dict[str, Any]) -> str:
    env = os.environ.get("COWORK_SSH_PASSWORD") or ""
    if env:
        return env
    direct = (data.get("ssh") or {}).get("password") or ""
    if direct:
        return direct
    for extra in (
        DEFAULT_PATH,
        Path(__file__).resolve().parent.parent / "cowork.local.json",
    ):
        if not extra.exists():
            continue
        try:
            other = json.loads(extra.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        pw = (other.get("ssh") or {}).get("password") or ""
        if pw:
            return pw
    return ""


def targets_from(data: dict[str, Any]) -> list[SSHTarget]:
    password = password_from(data)
    ssh = data.get("ssh") or {}
    host = ssh.get("host", "8.139.215.238")
    user = ssh.get("user", "root")
    become = ssh.get("become", "admin")
    out: list[SSHTarget] = []
    for agent in data.get("agents") or []:
        out.append(
            SSHTarget(
                id=agent["id"],
                host=agent.get("host", host),
                port=int(agent["port"]),
                user=agent.get("user", user),
                become=agent.get("become", become),
                password=password,
                workdir=agent.get("workdir", "/home/admin/cowork-bus"),
            )
        )
    return out
