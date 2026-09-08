import os

import pytest

from cowork.localcfg import load_config, targets_from
from cowork.sshutil import probe


pytestmark = pytest.mark.integration


def test_ssh_probe_three_agents():
    if not os.environ.get("COWORK_SSH_PASSWORD"):
        pytest.skip("COWORK_SSH_PASSWORD not set")
    cfg_path = os.environ.get("COWORK_CONFIG")
    data = load_config() if cfg_path else {
        "ssh": {
            "host": "8.139.215.238",
            "user": "root",
            "become": "admin",
            "password": os.environ["COWORK_SSH_PASSWORD"],
        },
        "agents": [
            {"id": "ac1", "port": 56735, "role": "planner"},
            {"id": "ac2", "port": 53326, "role": "builder"},
            {"id": "ac3", "port": 53730, "role": "reviewer"},
        ],
    }
    if not data.get("ssh"):
        data["ssh"] = {}
    data["ssh"]["password"] = os.environ["COWORK_SSH_PASSWORD"]
    targets = targets_from(data)
    assert len(targets) == 3
    for target in targets:
        info = probe(target)
        assert info["user"] == "admin"
        assert "Python" in info["detail"]
