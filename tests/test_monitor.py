import json
import threading
import time
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from cowork.live import assign_local, choose_assignee, parse_ps, unfinished
from cowork.monitor import make_handler
from cowork.protocol import AgentCard, Task
from cowork.runtime import wait_interval
from tests.conftest import make_store


PS = """
  536026       04:40 python3 -m cowork.runtime --agent-id ac1 --interval 20
  536120       03:55 /usr/local/bin/codex exec --dangerously-bypass-approvals-and-sandbox Brand: lienu Official start URL: https://www.lienujewelry.com/collections/all Image output
"""


def test_parse_ps_codex_and_runtime():
    parsed = parse_ps(PS)
    assert parsed["runtime"]["pid"] == 536026
    assert parsed["codex"]["brand"] == "lienu"
    assert "lienujewelry.com" in parsed["codex"]["url"]


def test_choose_assignee_prefers_idle_with_capability():
    task = {"id": "TASK-006", "type": "fetch", "status": "open"}
    agents = [
        {"id": "ac1", "online": True, "capabilities": ["fetch"], "busy": True, "codex": {"pid": 1}},
        {"id": "ac2", "online": True, "capabilities": ["fetch"], "busy": False, "codex": None},
        {"id": "ac3", "online": True, "capabilities": ["extract"], "busy": False, "codex": None},
    ]
    assert choose_assignee(task, agents) == "ac2"


def test_assign_local_and_unfinished(tmp_path):
    store = make_store(tmp_path)
    store.save_agent(AgentCard(id="ac2", role="fetcher", capabilities=["fetch"]))
    store.save_task(
        Task(id="TASK-006", scenario="crawler", type="fetch", title="synchronicity", status="failed", mode="browser")
    )
    assign_local(store, "TASK-006", "ac2")
    task = store.load_task("TASK-006")
    assert task.status == "claimed"
    assert task.owner == "ac2"
    assert store.load_claim("TASK-006").agent_id == "ac2"
    left = unfinished([task.to_dict()])
    assert left and left[0]["id"] == "TASK-006"


def test_wait_interval_wakes_on_file(tmp_path):
    store = make_store(tmp_path)
    card = AgentCard(id="ac1", role="fetcher", capabilities=["fetch"])
    store.save_agent(card)
    wake = store.inbox_dir("ac1") / "wake"
    threading.Timer(0.2, lambda: wake.write_text("1")).start()
    start = time.time()
    wait_interval(store, card, 20)
    assert time.time() - start < 5
    assert not wake.exists()


def test_monitor_http_snapshot_and_dispatch(tmp_path):
    snapshot = {
        "generated_at": 1,
        "project": {"name": "demo"},
        "root": str(tmp_path),
        "agents": [{"id": "ac1", "online": True, "busy": False}],
        "tasks": [{"id": "TASK-002", "status": "open", "type": "fetch", "title": "lienu"}],
        "unfinished": [{"id": "TASK-002", "status": "open"}],
    }
    posted = {}

    def snap():
        return snapshot

    def dispatch(body):
        posted.update(body)
        return {"ok": True, "results": [{"ok": True, "task_id": body.get("task_id"), "agent_id": "ac2"}]}

    handler = make_handler(snap, dispatch)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/")
        home = conn.getresponse()
        html = home.read().decode()
        assert home.status == 200
        assert "下发全部未完成" in html
        assert "任务描述" in html
        conn.request("GET", "/api/snapshot")
        data = json.loads(conn.getresponse().read())
        assert data["tasks"][0]["id"] == "TASK-002"
        conn.request("POST", "/api/dispatch", body=json.dumps({"task_id": "TASK-006", "agent_id": "ac2"}), headers={"Content-Type": "application/json"})
        result = json.loads(conn.getresponse().read())
        assert result["ok"] is True
        assert posted["task_id"] == "TASK-006"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_dispatch_unfinished_none_ready():
    from cowork.live import dispatch_tasks

    snap = {
        "agents": [{"id": "ac1", "online": True, "capabilities": ["fetch"], "busy": False}],
        "tasks": [{"id": "TASK-001", "status": "done", "type": "fetch"}],
    }
    result = dispatch_tasks({"unfinished": True}, cfg={"agents": []}, snapshot=snap)
    assert result["ok"] is True
    assert result["results"] == []
    assert "未完成" in result["message"]
