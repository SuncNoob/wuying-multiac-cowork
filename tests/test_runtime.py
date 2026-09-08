from cowork.project import init_project
from cowork.protocol import AgentCard, Task
from cowork.runtime import find_claimable, spawn_followups, tick, try_claim
from cowork.store import Store
from tests.conftest import git_init, make_store


def test_local_pipeline_coding(tmp_path):
    store = make_store(tmp_path)
    planner = AgentCard(id="ac1", role="planner", capabilities=["plan"])
    builder = AgentCard(id="ac2", role="builder", capabilities=["implement"])
    reviewer = AgentCard(id="ac3", role="reviewer", capabilities=["review"])
    store.save_agent(planner)
    store.save_agent(builder)
    store.save_agent(reviewer)
    store.save_task(
        Task(
            id="TASK-001",
            scenario="coding",
            type="plan",
            title="hello file",
            path="workspace/hello.txt",
            content="hello cowork\n",
            status="open",
        )
    )
    assert "claimed" in tick(store, planner)
    assert "executed" in tick(store, planner)
    assert "claimed" in tick(store, builder)
    assert "executed" in tick(store, builder)
    assert (tmp_path / "workspace/hello.txt").read_text() == "hello cowork\n"
    assert "claimed" in tick(store, reviewer)
    assert "executed" in tick(store, reviewer)
    assert store.load_task("TASK-003").status == "done"


def test_claim_conflict_second_agent_loses(tmp_path):
    store = make_store(tmp_path)
    a = AgentCard(id="ac2", role="builder", capabilities=["implement"])
    b = AgentCard(id="ac2b", role="builder", capabilities=["implement"])
    store.save_agent(a)
    store.save_agent(b)
    task = Task(id="TASK-001", scenario="coding", type="implement", title="t", path="a.txt", content="x")
    store.save_task(task)
    assert try_claim(store, a, task)
    assert not try_claim(store, b, store.load_task("TASK-001"))
    assert store.load_claim("TASK-001").agent_id == "ac2"


def test_find_claimable_respects_capability_and_deps(tmp_path):
    store = make_store(tmp_path)
    fetcher = AgentCard(id="ac2", role="fetcher", capabilities=["fetch"])
    store.save_agent(fetcher)
    store.save_task(
        Task(
            id="TASK-002",
            scenario="crawler",
            type="fetch",
            title="fetch",
            depends_on=["TASK-001"],
            status="open",
        )
    )
    assert find_claimable(store, fetcher) is None
    store.save_task(
        Task(id="TASK-001", scenario="crawler", type="enqueue", title="q", status="done")
    )
    found = find_claimable(store, fetcher)
    assert found is not None
    assert found.id == "TASK-002"


def test_spawn_followups_crawler(tmp_path):
    store = make_store(tmp_path)
    task = Task(
        id="TASK-001",
        scenario="crawler",
        type="enqueue",
        title="q",
        seed_urls=["https://example.com/"],
        allow_hosts=["example.com"],
        status="done",
    )
    store.save_task(task)
    created = spawn_followups(store, task, {"urls": ["https://example.com/"]})
    assert [t.type for t in created] == ["fetch", "extract"]
    assert created[1].depends_on == [created[0].id]


def test_project_init_cards(tmp_path):
    git_init(tmp_path)
    store = init_project(
        tmp_path,
        "demo",
        "crawler",
        [
            {"id": "ac1", "role": "dispatcher", "port": 1},
            {"id": "ac2", "role": "fetcher", "port": 2},
            {"id": "ac3", "role": "analyst", "port": 3},
        ],
    )
    assert store.load_project()["name"] == "demo"
    assert store.load_agent("ac2").capabilities == ["fetch"]
