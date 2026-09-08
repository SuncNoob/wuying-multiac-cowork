import json
from pathlib import Path

from cowork.cli import main


def test_cli_project_and_task(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "cowork.local.json"
    cfg.write_text(
        json.dumps(
            {
                "ssh": {"host": "127.0.0.1", "user": "root", "become": "admin"},
                "agents": [
                    {"id": "ac1", "port": 1, "role": "planner"},
                    {"id": "ac2", "port": 2, "role": "builder"},
                    {"id": "ac3", "port": 3, "role": "reviewer"},
                ],
            }
        )
    )
    monkeypatch.setenv("COWORK_CONFIG", str(cfg))
    assert main(["project", "create", "--name", "demo", "--scenario", "all"]) == 0
    assert (tmp_path / ".cowork/project.json").exists()
    assert main(
        [
            "task",
            "add",
            "--scenario",
            "coding",
            "--type",
            "plan",
            "--title",
            "hello",
            "--path",
            "workspace/hello.txt",
            "--content",
            "hi",
        ]
    ) == 0
    assert (tmp_path / ".cowork/tasks/TASK-001.json").exists()
    cards = json.loads((tmp_path / ".cowork/agents/ac2.json").read_text())
    assert "implement" in cards["capabilities"]
    assert "fetch" in cards["capabilities"]
