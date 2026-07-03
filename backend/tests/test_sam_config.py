import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_sam_template_defaults_to_local_persistence():
    template = (BACKEND_ROOT / "template.yaml").read_text(encoding="utf-8")

    assert "PersistenceMode:" in template
    assert "Default: local" in template
    assert "PERSISTENCE_MODE: !Ref PersistenceMode" in template
    assert "LOCAL_DATA_FILE: /tmp/lifeledger-reminders.json" in template


def test_sam_local_env_file_uses_local_persistence():
    env_file = json.loads((BACKEND_ROOT / "env.local.json").read_text(encoding="utf-8"))

    function_env = env_file["LifeLedgerApiFunction"]
    assert function_env["PERSISTENCE_MODE"] == "local"
    assert function_env["LOCAL_DATA_FILE"] == "/tmp/lifeledger-reminders.json"
