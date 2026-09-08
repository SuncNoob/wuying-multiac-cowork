from cowork.protocol import (
    AgentCard,
    Claim,
    Task,
    capabilities_for_role,
    claim_is_taken,
    host_allowed,
    make_claim,
    next_task_id,
)


def test_next_task_id_increments():
    assert next_task_id([]) == "TASK-001"
    assert next_task_id(["TASK-001", "TASK-007"]) == "TASK-008"


def test_role_capabilities():
    assert capabilities_for_role("fetcher") == ["fetch"]
    assert "implement" in capabilities_for_role("builder")


def test_can_handle():
    card = AgentCard(id="ac2", role="builder", capabilities=["implement"])
    assert card.can_handle("implement")
    assert not card.can_handle("fetch")


def test_claim_first_wins():
    claim = Claim(task_id="TASK-001", agent_id="ac1", claimed_at=1, lease_until=9_999_999_999)
    assert claim_is_taken(claim, "ac2")
    assert not claim_is_taken(claim, "ac1")
    assert not claim_is_taken(None, "ac1")


def test_expired_claim_is_free():
    claim = Claim(task_id="TASK-001", agent_id="ac1", claimed_at=1, lease_until=10)
    assert not claim_is_taken(claim, "ac2", at=11)


def test_make_claim_lease():
    claim = make_claim("TASK-001", "ac1", lease_seconds=30)
    assert claim.agent_id == "ac1"
    assert claim.lease_until >= claim.claimed_at + 30


def test_host_allowlist():
    allow = ["example.com"]
    assert host_allowed("https://example.com/x", allow)
    assert host_allowed("http://www.example.com/", allow)
    assert not host_allowed("https://evil.example.net/", allow)
    assert not host_allowed("file:///etc/passwd", allow)
    assert not host_allowed("https://example.com.evil.test/", allow)


def test_dependencies_done():
    parent = Task(id="TASK-001", scenario="crawler", type="fetch", title="f", status="done")
    child = Task(
        id="TASK-002",
        scenario="crawler",
        type="extract",
        title="e",
        depends_on=["TASK-001"],
    )
    assert child.dependencies_done({"TASK-001": parent})
    parent.status = "open"
    assert not child.dependencies_done({"TASK-001": parent})
