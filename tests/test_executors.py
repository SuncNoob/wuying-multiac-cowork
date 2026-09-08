from cowork.executors import run_enqueue, run_extract, run_fetch, run_implement, run_review
from cowork.protocol import Task, host_allowed
from tests.conftest import make_store


def test_implement_writes_file(tmp_path):
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="coding",
        type="implement",
        title="hello",
        path="workspace/hello.txt",
        content="hello cowork\n",
    )
    result = run_implement(store, task)
    assert result["ok"]
    assert (tmp_path / "workspace/hello.txt").read_text() == "hello cowork\n"


def test_implement_rejects_parent_path(tmp_path):
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="coding",
        type="implement",
        title="bad",
        path="../escape.txt",
        content="nope",
    )
    try:
        run_implement(store, task)
        assert False, "should have refused"
    except ValueError as exc:
        assert "refusing" in str(exc)


def test_review_pass_and_fail(tmp_path):
    store = make_store(tmp_path)
    impl = Task(
        id="TASK-001",
        scenario="coding",
        type="implement",
        title="hello",
        path="workspace/hello.txt",
        content="ok\n",
        status="done",
    )
    run_implement(store, impl)
    review = Task(
        id="TASK-002",
        scenario="coding",
        type="review",
        title="review",
        depends_on=["TASK-001"],
    )
    ok = run_review(store, review, {"TASK-001": impl})
    assert ok["ok"]
    missing = Task(
        id="TASK-003",
        scenario="coding",
        type="review",
        title="review missing",
        depends_on=["TASK-999"],
    )
    bad = run_review(store, missing, {})
    assert not bad["ok"]


def test_enqueue_requires_allow_hosts(tmp_path):
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="crawler",
        type="enqueue",
        title="seeds",
        seed_urls=["https://example.com/"],
        allow_hosts=[],
    )
    try:
        run_enqueue(store, task)
        assert False
    except ValueError:
        pass


def test_enqueue_filters_hosts(tmp_path):
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="crawler",
        type="enqueue",
        title="seeds",
        seed_urls=["https://example.com/", "https://evil.test/"],
        allow_hosts=["example.com"],
    )
    result = run_enqueue(store, task)
    assert result["urls"] == ["https://example.com/"]
    assert result["rejected"] == ["https://evil.test/"]
    assert not host_allowed("https://evil.test/", ["example.com"])


def test_fetch_and_extract_with_stub(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    html = b"<html><title>Example Domain</title><body>ok</body></html>"
    monkeypatch.setattr(
        "cowork.executors.fetch_url",
        lambda url, timeout=20: (200, "text/html", html),
    )
    enqueue = Task(
        id="TASK-001",
        scenario="crawler",
        type="enqueue",
        title="seeds",
        seed_urls=["https://example.com/"],
        allow_hosts=["example.com"],
        status="done",
    )
    run_enqueue(store, enqueue)
    fetch = Task(
        id="TASK-002",
        scenario="crawler",
        type="fetch",
        title="fetch",
        depends_on=["TASK-001"],
        seed_urls=["https://example.com/"],
        allow_hosts=["example.com"],
    )
    fetched = run_fetch(store, fetch)
    assert fetched["ok"]
    assert fetched["fetched"][0]["title"] == "Example Domain"
    extract = Task(
        id="TASK-003",
        scenario="crawler",
        type="extract",
        title="extract",
        depends_on=["TASK-002"],
    )
    out = run_extract(store, extract, {"TASK-002": fetch})
    assert out["ok"]
    jsonl = (tmp_path / out["file"]).read_text()
    assert "Example Domain" in jsonl


def test_fetch_skips_disallowed_host(tmp_path, monkeypatch):
    called = []

    def boom(url, timeout=20):
        called.append(url)
        return 200, "text/html", b"nope"

    monkeypatch.setattr("cowork.executors.fetch_url", boom)
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="crawler",
        type="fetch",
        title="fetch",
        seed_urls=["https://evil.test/secret"],
        allow_hosts=["example.com"],
    )
    result = run_fetch(store, task)
    assert called == []
    assert result["fetched"][0]["ok"] is False
    assert "not allowed" in result["fetched"][0]["error"]
