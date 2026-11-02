import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def cli(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "scripts/backend_admin.py"
    spec = importlib.util.spec_from_file_location("backend_admin_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = Mock()
    repo.get.return_value = {"isActive": True, "role": "user"}
    monkeypatch.setattr(
        module, "get_settings", lambda: SimpleNamespace(firebase_project_id="demo-legal-api")
    )
    initialize = Mock(return_value={"db": Mock(), "storage": Mock()})
    monkeypatch.setattr(module, "initialize_firebase", initialize)
    monkeypatch.setattr(module, "BackendRepository", lambda _: repo)
    monkeypatch.setattr(module.auth, "get_user", Mock(return_value=SimpleNamespace(disabled=False)))
    return module, repo, initialize


def test_cli_project_mismatch_does_not_access_firebase(cli, monkeypatch):
    module, repo, initialize = cli
    monkeypatch.setattr(
        "sys.argv",
        ["backend_admin", "--project", "wrong", "--apply", "grant-admin", "--uid", "uid"],
    )
    with pytest.raises(SystemExit):
        module.main()
    initialize.assert_not_called()
    repo.mutate.assert_not_called()


def test_admin_cli_is_dry_run_by_default(cli, monkeypatch, capsys):
    module, repo, _ = cli
    monkeypatch.setattr(
        "sys.argv", ["backend_admin", "--project", "demo-legal-api", "grant-admin", "--uid", "uid"]
    )
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["dryRun"] is True
    repo.mutate.assert_not_called()


def test_admin_cli_apply_uses_audited_mutation(cli, monkeypatch):
    module, repo, _ = cli
    monkeypatch.setattr(
        "sys.argv",
        ["backend_admin", "--project", "demo-legal-api", "--apply", "grant-admin", "--uid", "uid"],
    )
    assert module.main() == 0
    args, kwargs = repo.mutate.call_args
    assert args[:2] == ("users", "uid")
    assert args[2]({"isActive": True, "role": "user"}) == {"role": "admin"}
    assert args[2]({"isActive": True, "role": "admin"}) is None
    assert kwargs["event"] == "user.admin_granted"


def test_admin_cli_refuses_inactive_account(cli, monkeypatch):
    module, repo, _ = cli
    repo.get.return_value = {"isActive": False, "role": "user"}
    monkeypatch.setattr(
        "sys.argv",
        ["backend_admin", "--project", "demo-legal-api", "--apply", "grant-admin", "--uid", "uid"],
    )
    with pytest.raises(SystemExit):
        module.main()
    repo.mutate.assert_not_called()


def test_reconcile_cli_error_exit_and_dry_run(cli, monkeypatch, capsys):
    module, repo, _ = cli
    reconcile = Mock(return_value={"errors": 1})
    monkeypatch.setattr(module, "reconcile", reconcile)
    monkeypatch.setattr(module.knowledge, "reconcile", Mock(return_value={"errors": 0}))
    monkeypatch.setattr("sys.argv", ["backend_admin", "--project", "demo-legal-api", "reconcile"])
    assert module.main() == 1
    assert reconcile.call_args.kwargs["dry_run"] is True
    assert json.loads(capsys.readouterr().out)["shared"]["errors"] == 1
