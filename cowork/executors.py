"""Scenario executors. Stdlib only so they run on 无影 AC without pip."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from cowork.protocol import Task, dump_json, host_allowed, now
from cowork.store import Store

USER_AGENT = "Cowork/0.1 (+https://github.com/wuying-multiac-cowork)"


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def fetch_url(url: str, timeout: int = 20) -> tuple[int, str, bytes]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:  # nosec B310 - scheme checked by host_allowed
        body = resp.read()
        return int(getattr(resp, "status", 200) or 200), str(resp.headers.get("Content-Type", "")), body


def extract_title(html: bytes) -> str:
    parser = _TitleParser()
    try:
        parser.feed(html.decode("utf-8", "replace"))
    except Exception:
        return ""
    return parser.title.strip()


def run_implement(store: Store, task: Task) -> dict:
    if not task.path:
        raise ValueError("implement task missing path")
    rel = Path(task.path)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"refusing path outside workspace: {task.path}")
    dest = (store.root / rel).resolve()
    if dest != store.root.resolve() and store.root.resolve() not in dest.parents:
        raise ValueError(f"refusing path outside workspace: {task.path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(task.content if task.content else f"{task.title}\n{task.body}\n", encoding="utf-8")
    result = {
        "ok": True,
        "path": task.path,
        "bytes": dest.stat().st_size,
        "at": now(),
    }
    dump_json(store.result_dir(task.id) / "implement.json", result)
    return result


def run_review(store: Store, task: Task, tasks: dict[str, Task]) -> dict:
    notes: list[str] = []
    ok = True
    for dep in task.depends_on:
        parent = tasks.get(dep)
        if parent is None:
            ok = False
            notes.append(f"missing dependency {dep}")
            continue
        if parent.path:
            target = store.root / parent.path
            if not target.exists():
                ok = False
                notes.append(f"missing file {parent.path}")
            else:
                notes.append(f"found {parent.path} ({target.stat().st_size} bytes)")
        implement = store.result_dir(dep) / "implement.json"
        if implement.exists():
            notes.append(f"implement result present for {dep}")
        else:
            ok = False
            notes.append(f"no implement result for {dep}")
    result = {"ok": ok, "notes": notes, "at": now()}
    dump_json(store.result_dir(task.id) / "review.json", result)
    (store.result_dir(task.id) / "review.md").write_text(
        ("PASS" if ok else "FAIL") + "\n" + "\n".join(notes) + "\n",
        encoding="utf-8",
    )
    return result


def run_enqueue(store: Store, task: Task) -> dict:
    if not task.seed_urls:
        raise ValueError("enqueue task has no seed_urls")
    if not task.allow_hosts:
        raise ValueError("enqueue task requires allow_hosts")
    accepted: list[str] = []
    rejected: list[str] = []
    for url in task.seed_urls:
        if host_allowed(url, task.allow_hosts):
            accepted.append(url)
        else:
            rejected.append(url)
    payload = {
        "seed_task": task.id,
        "allow_hosts": task.allow_hosts,
        "urls": accepted,
        "rejected": rejected,
        "at": now(),
    }
    dump_json(store.cowork / "queue" / f"{task.id}.json", payload)
    dump_json(store.result_dir(task.id) / "enqueue.json", payload)
    return payload


def run_fetch(store: Store, task: Task) -> dict:
    queue = _queue_for(store, task)
    allow_hosts = task.allow_hosts or queue.get("allow_hosts") or []
    urls = task.seed_urls or queue.get("urls") or []
    if not urls:
        raise ValueError("fetch task has no urls")
    fetched = []
    for url in urls:
        if not host_allowed(url, allow_hosts):
            fetched.append({"url": url, "ok": False, "error": "host not allowed"})
            continue
        try:
            status, content_type, body = fetch_url(url)
            raw_path = store.result_dir(task.id) / _safe_name(url)
            raw_path.write_bytes(body)
            fetched.append(
                {
                    "url": url,
                    "ok": True,
                    "status": status,
                    "content_type": content_type,
                    "bytes": len(body),
                    "file": str(raw_path.relative_to(store.root)),
                    "title": extract_title(body),
                }
            )
        except (URLError, TimeoutError, ValueError, OSError) as exc:
            fetched.append({"url": url, "ok": False, "error": str(exc)})
    result = {"ok": all(item.get("ok") for item in fetched), "fetched": fetched, "at": now()}
    dump_json(store.result_dir(task.id) / "fetch.json", result)
    return result


def run_extract(store: Store, task: Task, tasks: dict[str, Task]) -> dict:
    rows = []
    for dep in task.depends_on:
        fetch_result = store.result_dir(dep) / "fetch.json"
        if not fetch_result.exists():
            continue
        data = json.loads(fetch_result.read_text(encoding="utf-8"))
        for item in data.get("fetched") or []:
            rows.append(
                {
                    "source_task": dep,
                    "url": item.get("url"),
                    "ok": item.get("ok"),
                    "status": item.get("status"),
                    "title": item.get("title"),
                    "bytes": item.get("bytes"),
                }
            )
    jsonl = store.result_dir(task.id) / "structured.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    result = {"ok": bool(rows) and all(r.get("ok") for r in rows), "rows": len(rows), "file": str(jsonl.relative_to(store.root)), "at": now()}
    dump_json(store.result_dir(task.id) / "extract.json", result)
    return result


def _queue_for(store: Store, task: Task) -> dict:
    for dep in task.depends_on:
        q = store.cowork / "queue" / f"{dep}.json"
        if q.exists():
            return json.loads(q.read_text(encoding="utf-8"))
    files = sorted((store.cowork / "queue").glob("*.json"))
    if files:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    return {}


def _safe_name(url: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in url)
    return (cleaned[:80] or "page") + ".html"
