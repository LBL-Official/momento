"""Live unit and deploy scripts stay fail-closed. Process up is not submit."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / "deploy" / "momento-live.service"
BUILD = ROOT / "deploy" / "mlb001-arm64-build.sh"
DEPLOY = ROOT / "deploy" / "mlb001-atomic-deploy.sh"
RECOVER = ROOT / "deploy" / "mlb001-recover-baseline.sh"
BASELINE = ROOT / "deploy" / "mlb001-production-baseline.json"
BASELINE_SHA = "66ca5420273779b6706e873c4a6640ef4fd603dd0bb02e9d044ee18077c2f3fd"
HISTORICAL_SHA = "fb939b622483553a5cb7d9c066944c5ec0065290d2eae9d478e71f078e9e00f8"


def test_live_unit_restarts_process_not_trading_gate():
    text = UNIT.read_text(encoding="utf-8")
    assert "Restart=always" in text
    assert "RestartPreventExitStatus=78" in text
    assert "StartLimitIntervalSec=300" in text
    assert "StartLimitBurst=10" in text
    assert "Restart=on-failure" not in text


def test_atomic_deploy_requires_recon_cleared_and_can_rollback():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "housekeeping_ok" in text
    assert "recon_cleared" in text
    assert "order_submission=enabled" in text
    assert "rollback" in text
    assert "VITAL_AWS_CONTROL" in text
    assert "live.toml" in text
    assert BUILD.is_file()
    assert "cargo test -p momento-positions --test tracker" in BUILD.read_text(encoding="utf-8")


def test_production_baseline_is_current_sha_not_sep13():
    import json

    ident = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert ident["binary"]["sha256"] == BASELINE_SHA
    assert ident["historical_not_baseline"]["sha256"] == HISTORICAL_SHA
    assert ident["binary"]["sha256"] != ident["historical_not_baseline"]["sha256"]
    assert ident["strategy"]["entry"] == "80_to_81_yes_bid"
    assert ident["strategy"]["cap"] == 5
    recover = RECOVER.read_text(encoding="utf-8")
    assert BASELINE_SHA in recover
    assert "mlb001-atomic-deploy.sh" in recover
    assert "fb939b62" not in recover or "not" in recover.lower()
    doc = (ROOT / "docs" / "operations" / "MLB001_PRODUCTION_BASELINE.md").read_text(encoding="utf-8")
    assert BASELINE_SHA in doc
    assert "Do not recover from it" in doc
