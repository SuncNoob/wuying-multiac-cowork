"""Live Agent Computer snapshot and task dispatch for the local monitor."""

from __future__ import annotations

import base64
import json
import re
import shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from cowork.codex_run import CODEX_LEASE_SECONDS
from cowork.describe import describe_task
from cowork.localcfg import load_config, targets_from
from cowork.protocol import DEFAULT_LEASE_SECONDS, Task, make_claim, now
from cowork.sshutil import Remote, SSHTarget
from cowork.store import GitError, Store

UNFINISHED_STATUSES = {"open", "failed", "claimed"}
BRAND_RE = re.compile(r"Brand:\s+(\S+)")
URL_RE = re.compile(r"Official start URL:\s+(\S+)")

SNAPSHOT_PY = r"""
import json, pathlib, subprocess, time
workdir = WORKDIR
agent_id = AGENT_ID
out = {
    "id": agent_id,
    "online": True,
    "error": "",
    "cwd": workdir,
    "heartbeat_at": 0,
    "role": "",
    "capabilities": [],
    "runtime": None,
    "codex": None,
    "tasks": [],
    "pics": [],
    "git_head": "",
    "git_status": "",
}
try:
    ps = subprocess.run(
        ["ps", "-u", "admin", "-o", "pid,etime,cmd"],
        capture_output=True, text=True, timeout=8,
    )
    out["ps"] = ps.stdout
except Exception as exc:
    out["ps"] = ""
    out["error"] = str(exc)
root = pathlib.Path(workdir)
try:
    head = subprocess.run(
        ["git", "log", "-1", "--format=%h %s"],
        cwd=workdir, capture_output=True, text=True, timeout=8,
    )
    out["git_head"] = (head.stdout or "").strip()
    st = subprocess.run(
        ["git", "status", "-sb"],
        cwd=workdir, capture_output=True, text=True, timeout=8,
    )
    out["git_status"] = (st.stdout or "").splitlines()[0] if st.stdout else ""
except Exception:
    pass
tasks_dir = root / ".cowork" / "tasks"
if tasks_dir.is_dir():
    for path in sorted(tasks_dir.glob("TASK-*.json")):
        try:
            out["tasks"].append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            out["tasks"].append({"id": path.stem, "status": "invalid", "title": path.name})
agent_path = root / ".cowork" / "agents" / f"{agent_id}.json"
if agent_path.exists():
    try:
        card = json.loads(agent_path.read_text(encoding="utf-8"))
        out["role"] = card.get("role") or ""
        out["capabilities"] = card.get("capabilities") or []
        out["heartbeat_at"] = int(card.get("heartbeat_at") or 0)
    except Exception:
        pass
pics = root / "pics"
if pics.is_dir():
    for path in sorted(pics.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            out["pics"].append(str(path.relative_to(root)))
print(json.dumps(out, ensure_ascii=False))
"""

DISPATCH_PY = r"""
import json, pathlib, sys, time
from cowork.codex_run import CODEX_LEASE_SECONDS
from cowork.protocol import DEFAULT_LEASE_SECONDS, make_claim, now
from cowork.store import GitError, Store

task_id = TASK_ID
agent_id = AGENT_ID
reopen_only = REOPEN_ONLY
force = FORCE
store = Store(pathlib.Path(WORKDIR))
store.ensure_layout()
try:
    store.pull()
except GitError:
    pass
task = store.load_task(task_id)
if task is None:
    print(json.dumps({"ok": False, "error": f"missing {task_id}"}))
    raise SystemExit(0)
if task.status == "done" and not force:
    print(json.dumps({"ok": False, "error": f"{task_id} already done"}))
    raise SystemExit(0)
if task.status == "in_progress" and task.owner and task.owner != agent_id and not force and not reopen_only:
    print(json.dumps({"ok": False, "error": f"{task_id} in_progress on {task.owner}"}))
    raise SystemExit(0)
if reopen_only or not agent_id:
    task.status = "open"
    task.owner = ""
    store.clear_claim(task_id)
    store.save_task(task)
    msg = f"cowork(monitor): reopen {task_id}"
else:
    lease = CODEX_LEASE_SECONDS if (task.mode or "") == "browser" else DEFAULT_LEASE_SECONDS
    task.status = "claimed"
    task.owner = agent_id
    store.save_task(task)
    store.save_claim(make_claim(task_id, agent_id, lease_seconds=lease))
    msg = f"cowork(monitor): dispatch {task_id} -> {agent_id}"
try:
    store.sync_push(msg)
except GitError as exc:
    print(json.dumps({"ok": False, "error": str(exc)}))
    raise SystemExit(0)
wake = store.inbox_dir(agent_id) / "wake" if agent_id else None
if wake is not None:
    wake.write_text(str(int(time.time())), encoding="utf-8")
print(json.dumps({"ok": True, "task_id": task_id, "agent_id": agent_id, "status": task.status}))
"""


def parse_ps(text: str) -> dict[str, Any]:
    runtime = None
    codex = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid_s, etime, cmd = parts
        if not pid_s.isdigit():
            continue
        pid = int(pid_s)
        if "cowork.runtime" in cmd and "grep" not in cmd:
            runtime = {"pid": pid, "etime": etime, "alive": True}
        elif "/codex exec" in cmd or cmd.startswith("codex exec") or "codex exec " in cmd:
            brand_m = BRAND_RE.search(cmd)
            url_m = URL_RE.search(cmd)
            codex = {
                "pid": pid,
                "etime": etime,
                "alive": True,
                "brand": brand_m.group(1) if brand_m else "",
                "url": url_m.group(1) if url_m else "",
            }
    return {"runtime": runtime, "codex": codex}


def bus_root(cfg: dict[str, Any], explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    cwd = Path.cwd()
    remote = (cfg.get("github") or {}).get("remote") or ""
    home_jewelry = Path.home() / "japan-jewelry-pics"
    sibling = Path(__file__).resolve().parent.parent.parent / "japan-jewelry-pics"
    if "japan-jewelry-pics" in remote:
        for candidate in (home_jewelry, sibling, cwd):
            if (candidate / ".cowork" / "project.json").exists():
                return candidate
    if (cwd / ".cowork" / "project.json").exists():
        return cwd
    return cwd


def unfinished(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tasks if str(t.get("status") or "") in UNFINISHED_STATUSES]


def task_ready(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    for dep in task.get("depends_on") or []:
        parent = by_id.get(dep) or {}
        if parent.get("status") != "done":
            return False
    return True


def agent_busy(agent: dict[str, Any]) -> bool:
    if agent.get("codex"):
        return True
    current = agent.get("current_task") or {}
    return current.get("status") in {"claimed", "in_progress"}


def choose_assignee(task: dict[str, Any], agents: list[dict[str, Any]], idle_only: bool = True) -> str:
    kind = str(task.get("type") or "")
    candidates = []
    for agent in agents:
        if not agent.get("online"):
            continue
        caps = agent.get("capabilities") or []
        if kind and kind not in caps:
            continue
        if idle_only and agent_busy(agent):
            continue
        candidates.append(agent)
    if not candidates:
        return ""
    candidates.sort(key=lambda a: (agent_busy(a), a.get("id") or ""))
    return str(candidates[0]["id"])


def _current_task(agent_id: str, tasks: list[dict[str, Any]], codex: dict[str, Any] | None) -> dict[str, Any] | None:
    owned = [
        t
        for t in tasks
        if t.get("owner") == agent_id and t.get("status") in {"claimed", "in_progress"}
    ]
    if owned:
        return owned[0]
    if not codex:
        return None
    brand = (codex.get("brand") or "").lower()
    for t in tasks:
        if str(t.get("brand") or "").lower() == brand and t.get("status") in {"claimed", "in_progress", "open"}:
            return t
    return None


def _b64_exec(script: str, replacements: dict[str, Any]) -> str:
    text = script
    for key, value in replacements.items():
        if isinstance(value, bool):
            text = text.replace(key, "True" if value else "False")
        else:
            text = text.replace(key, json.dumps(value))
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    inner = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "').decode())\""
    workdir = replacements.get("WORKDIR")
    if isinstance(workdir, str) and workdir:
        return f"cd {shlex.quote(workdir)} && PYTHONPATH=. {inner}"
    return inner


def probe_agent(target: SSHTarget) -> dict[str, Any]:
    fallback = {
        "id": target.id,
        "online": False,
        "error": "",
        "role": "",
        "capabilities": [],
        "heartbeat_at": 0,
        "runtime": None,
        "codex": None,
        "current_task": None,
        "busy": False,
        "pics": [],
        "git_head": "",
        "git_status": "",
        "tasks": [],
        "cwd": target.workdir,
    }
    try:
        with Remote(target) as remote:
            cmd = _b64_exec(SNAPSHOT_PY, {"WORKDIR": target.workdir, "AGENT_ID": target.id})
            code, out, err = remote.run(cmd, timeout=25)
    except Exception as exc:
        fallback["error"] = str(exc)
        return fallback
    payload = out.strip().splitlines()
    raw = ""
    for line in reversed(payload):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            raw = line
            break
    if not raw:
        fallback["error"] = (err or out or f"exit {code}")[:400]
        return fallback
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        fallback["error"] = "invalid snapshot json"
        return fallback
    parsed = parse_ps(data.get("ps") or "")
    tasks = list(data.get("tasks") or [])
    data["runtime"] = parsed["runtime"]
    data["codex"] = parsed["codex"]
    data["current_task"] = _current_task(target.id, tasks, parsed["codex"])
    data["busy"] = bool(parsed["codex"]) or (
        (data["current_task"] or {}).get("status") in {"claimed", "in_progress"}
    )
    data["online"] = True
    data["error"] = data.get("error") or ""
    if not data.get("runtime"):
        data["error"] = data["error"] or "coworkd not running"
    return data


def collect_snapshot(cfg: dict[str, Any] | None = None, root: Path | None = None) -> dict[str, Any]:
    cfg = cfg if cfg is not None else load_config()
    targets = targets_from(cfg)
    agents: list[dict[str, Any]] = []
    errors: list[str] = []
    if targets:
        with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
            futs = {pool.submit(probe_agent, t): t.id for t in targets}
            by_id: dict[str, dict[str, Any]] = {}
            for fut in as_completed(futs):
                by_id[futs[fut]] = fut.result()
            agents = [by_id[t.id] for t in targets]
    tasks: list[dict[str, Any]] = []
    for agent in agents:
        if agent.get("online") and agent.get("tasks"):
            tasks = list(agent["tasks"])
            break
    if not tasks:
        bus = root or bus_root(cfg)
        store = Store(bus)
        for task in store.all_tasks().values():
            tasks.append(task.to_dict())
        project = store.load_project()
    else:
        bus = root or bus_root(cfg)
        project = Store(bus).load_project() if (bus / ".cowork" / "project.json").exists() else {}
        if not project:
            project = {"name": Path(targets[0].workdir).name if targets else "cowork"}
    by_id = {str(t.get("id")): t for t in tasks}
    for task in tasks:
        task["description"] = describe_task(task)
    for agent in agents:
        current = agent.get("current_task")
        if current:
            current["description"] = describe_task(current)
        if agent.get("heartbeat_at"):
            agent["heartbeat_age_s"] = max(0, now() - int(agent["heartbeat_at"]))
        else:
            agent["heartbeat_age_s"] = None
    return {
        "generated_at": now(),
        "project": project,
        "root": str(bus),
        "agents": agents,
        "tasks": tasks,
        "unfinished": unfinished(tasks),
        "errors": errors,
    }


def _target_map(cfg: dict[str, Any]) -> dict[str, SSHTarget]:
    return {t.id: t for t in targets_from(cfg)}


def _run_dispatch(target: SSHTarget, task_id: str, agent_id: str, reopen_only: bool, force: bool) -> dict[str, Any]:
    cmd = _b64_exec(
        DISPATCH_PY,
        {
            "WORKDIR": target.workdir,
            "TASK_ID": task_id,
            "AGENT_ID": agent_id,
            "REOPEN_ONLY": reopen_only,
            "FORCE": force,
        },
    )
    with Remote(target) as remote:
        code, out, err = remote.run(cmd, timeout=90)
    raw = ""
    for line in reversed((out or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            raw = line
            break
    if not raw:
        return {"ok": False, "error": (err or out or f"exit {code}")[:500]}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid dispatch json"}
    return data


def dispatch_tasks(
    body: dict[str, Any],
    cfg: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg if cfg is not None else load_config()
    snapshot = snapshot if snapshot is not None else collect_snapshot(cfg)
    agents = list(snapshot.get("agents") or [])
    tasks = list(snapshot.get("tasks") or [])
    by_id = {str(t.get("id")): t for t in tasks}
    force = bool(body.get("force"))
    reopen_only = bool(body.get("reopen"))
    wanted: list[str] = []
    if body.get("unfinished"):
        for task in unfinished(tasks):
            if task_ready(task, by_id) or force:
                wanted.append(str(task["id"]))
        if not wanted:
            return {"ok": True, "results": [], "message": "没有可下发的未完成任务"}
    elif body.get("task_id"):
        wanted = [str(body["task_id"])]
    else:
        return {"ok": False, "error": "task_id or unfinished required"}
    targets = _target_map(cfg)
    if not targets:
        return {"ok": False, "error": "no agents in local config"}

    results = []
    assigned_now: set[str] = set()
    for task_id in wanted:
        task = by_id.get(task_id)
        if task is None:
            results.append({"task_id": task_id, "ok": False, "error": "unknown task"})
            continue
        agent_id = str(body.get("agent_id") or "")
        if reopen_only:
            agent_id = agent_id or next((a["id"] for a in agents if a.get("online")), next(iter(targets)))
            runner = targets.get(agent_id)
            if runner is None:
                results.append({"task_id": task_id, "ok": False, "error": "no ssh target"})
                continue
            result = _run_dispatch(runner, task_id, "", True, force)
            results.append(result)
            continue
        if not agent_id:
            idle_agents = [
                a for a in agents if a.get("id") not in assigned_now
            ]
            agent_id = choose_assignee(task, idle_agents, idle_only=True)
            if not agent_id:
                agent_id = choose_assignee(task, agents, idle_only=False)
        if not agent_id:
            results.append({"task_id": task_id, "ok": False, "error": "no capable agent"})
            continue
        runner = targets.get(agent_id) or targets.get(next(iter(targets)))
        if runner is None:
            results.append({"task_id": task_id, "ok": False, "error": "no ssh target"})
            continue
        result = _run_dispatch(runner, task_id, agent_id, False, force)
        if result.get("ok"):
            assigned_now.add(agent_id)
            for agent in agents:
                if agent.get("id") == agent_id:
                    agent["busy"] = True
        results.append(result)
    ok = any(r.get("ok") for r in results) if results else False
    return {"ok": ok, "results": results}


def assign_local(store: Store, task_id: str, agent_id: str, reopen_only: bool = False) -> Task:
    """Pure local assign used by tests. Does not SSH."""
    task = store.load_task(task_id)
    if task is None:
        raise KeyError(task_id)
    if reopen_only:
        task.status = "open"
        task.owner = ""
        store.clear_claim(task_id)
        store.save_task(task)
        return task
    lease = CODEX_LEASE_SECONDS if task.mode == "browser" else DEFAULT_LEASE_SECONDS
    task.status = "claimed"
    task.owner = agent_id
    store.save_task(task)
    store.save_claim(make_claim(task_id, agent_id, lease_seconds=lease))
    return task
