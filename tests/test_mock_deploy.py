import json
from pathlib import Path

import pytest

from ai_observability import mock_deploy
from ai_observability.mock_deploy import run_preflight, write_json

ROOT = Path(__file__).parent.parent


def test_mock_deploy_preflight_generates_review_only_evidence() -> None:
    report, package = run_preflight(ROOT / "deployment/mock-deploy.json", ROOT)

    assert report["result"] == "passed"
    assert report["review_outcome"]["disposition"] == "review_required"
    assert report["review_outcome"]["enforcement_performed"] is False
    assert package["retention_mode"] == "metadata_and_hashes_only"


def test_mock_deploy_preflight_rejects_a_missing_artifact(tmp_path: Path) -> None:
    config = json.loads((ROOT / "deployment/mock-deploy.json").read_text(encoding="utf-8"))
    config["policy_file"] = "policy/missing.json"
    config_path = tmp_path / "mock-deploy.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        run_preflight(config_path, ROOT)


def test_write_json_does_not_overwrite_evidence(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    write_json(report_path, {"result": "passed"})

    with pytest.raises(FileExistsError):
        write_json(report_path, {"result": "changed"})


def test_cli_rejects_existing_output_before_writing_any_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "report.json"
    package_path = tmp_path / "package.json"
    package_path.write_text("existing package", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "veyepr-mock-deploy",
            "--config",
            str(ROOT / "deployment/mock-deploy.json"),
            "--repository-root",
            str(ROOT),
            "--report",
            str(report_path),
            "--audit-package",
            str(package_path),
        ],
    )

    with pytest.raises(FileExistsError):
        mock_deploy.main()

    assert not report_path.exists()
