"""Install cowork runtime onto 无影 AC over SSH and start coworkd."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

from cowork.sshutil import Remote, SSHTarget

SKIP_DIRS = {".git", ".venv", ".pytest_cache", "__pycache__", ".mypy_cache"}
SKIP_FILES = {"cowork.local.json"}


def pack_payload(root: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if rel.name in SKIP_FILES or rel.name.endswith(".pyc"):
                continue
            tar.add(path, arcname=str(rel))
    return buf.getvalue()


def install_agent(
    target: SSHTarget,
    repo_root: Path,
    git_remote: str,
    deploy_key: str | None = None,
    start: bool = True,
) -> str:
    tarball = pack_payload(repo_root)
    workdir = target.workdir
    with Remote(target) as remote:
        remote.run_root(f"mkdir -p {workdir} /home/admin/.ssh /home/admin/logs && chown -R {target.become}:{target.become} /home/admin/.ssh /home/admin/logs {workdir}")
        remote.put_bytes(tarball, f"/tmp/cowork-{target.id}.tgz", mode=0o644)
        code, out, err = remote.run(
            f"mkdir -p {workdir} && tar -xzf /tmp/cowork-{target.id}.tgz -C {workdir}",
            timeout=120,
        )
        if code != 0:
            raise RuntimeError(err or out)
        if deploy_key:
            remote.put_bytes(
                deploy_key.encode("utf-8"),
                "/home/admin/.ssh/cowork_deploy",
                mode=0o600,
            )
            ssh_config = (
                "Host github.com\n"
                "  IdentityFile ~/.ssh/cowork_deploy\n"
                "  StrictHostKeyChecking accept-new\n"
            )
            remote.put_bytes(ssh_config.encode("utf-8"), "/home/admin/.ssh/config", mode=0o600)
        git_ssh = "GIT_SSH_COMMAND='ssh -i /home/admin/.ssh/cowork_deploy -o StrictHostKeyChecking=accept-new'"
        if git_remote:
            clone = (
                f"rm -rf {workdir} && mkdir -p {workdir} && "
                f"{git_ssh} git clone {git_remote} {workdir}"
            )
            code, out, err = remote.run(clone, timeout=180)
            if code != 0:
                # fall back to tarball overlay
                remote.run(f"mkdir -p {workdir} && tar -xzf /tmp/cowork-{target.id}.tgz -C {workdir}", timeout=120)
        else:
            code, out, err = remote.run(
                f"mkdir -p {workdir} && tar -xzf /tmp/cowork-{target.id}.tgz -C {workdir}",
                timeout=120,
            )
            if code != 0:
                raise RuntimeError(err or out)
        git_setup = (
            f"cd {workdir} && "
            "git init >/dev/null 2>&1 || true; "
            f"git config user.name {target.id}; "
            f"git config user.email {target.id}@cowork.local; "
        )
        if git_remote:
            git_setup += (
                "git remote remove origin >/dev/null 2>&1 || true; "
                f"git remote add origin {git_remote} >/dev/null 2>&1 || git remote set-url origin {git_remote}; "
                "git branch -M main; "
            )
        remote.run(git_setup, timeout=60)
        if start:
            start_cmd = (
                f"cd {workdir} && "
                "mkdir -p /home/admin/logs && "
                f"(pkill -f 'python3 -m cowork.runtime --agent-id {target.id}' || true); "
                "nohup env PYTHONPATH=. python3 -m cowork.runtime "
                f"--agent-id {target.id} --interval 12 "
                f"> /home/admin/logs/coworkd-{target.id}.log 2>&1 & echo $!"
            )
            code, out, err = remote.run(start_cmd, timeout=30)
            if code != 0:
                raise RuntimeError(err or out)
            return out.strip()
    return "installed"


def doctor_agent(target: SSHTarget) -> dict[str, str]:
    with Remote(target) as remote:
        code, out, err = remote.run(
            f"whoami; test -d {target.workdir} && echo HAS_WORKDIR; "
            f"pgrep -af cowork.runtime || true; "
            f"tail -n 20 /home/admin/logs/coworkd-{target.id}.log 2>/dev/null || true"
        )
        return {"code": str(code), "out": out, "err": err}
