"""NBA Bot 001 unit and deploy scripts stay separate from MLB and fail closed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / "deploy" / "momento-nba-001.service"
BUILD = ROOT / "deploy" / "nba001-arm64-build.sh"
DEPLOY = ROOT / "deploy" / "nba001-atomic-deploy.sh"
FETCH = ROOT / "deploy" / "nba001-fetch-secret.sh"


def test_unit_is_its_own_service_and_restarts_except_fail_closed():
    text = UNIT.read_text(encoding="utf-8")
    assert "ExecStart=/usr/local/bin/momento-nba-001 run" in text
    assert "Restart=always" in text
    assert "RestartPreventExitStatus=78" in text
    assert "MemoryMax=" in text
    assert "ReadWritePaths=/var/lib/momento/nba-001" in text
    assert "/dev/shm/momento-kalshi-nba-001.json" in text
    assert "momento-trading-engine" not in text
    assert "momento-kalshi-live.json" not in text
    assert "/var/lib/momento/state" not in text
    assert "Conflicts=momento-live" not in text


def test_fetch_refuses_shared_secret_path_and_never_prints():
    text = FETCH.read_text(encoding="utf-8")
    assert "set +x" in text
    assert "/dev/shm/momento-kalshi-nba-001.json) ;;" in text
    assert "exit 78" in text
    assert "echo \"$" not in text.split("aws secretsmanager")[1].split("mv ")[0]


def test_build_refuses_production_order_path():
    # Behaviour change (2026-09-27): the NBA order adapter is now linked for
    # fixture and demo use, so the gate moved from "no order symbols" to
    # "production submission compiled out and never constructed".
    text = BUILD.read_text(encoding="utf-8")
    assert "pub const PRODUCTION_ORDERS_COMPILED: bool = false;" in text
    assert "assert!(!PRODUCTION_ORDERS_COMPILED)" in text
    assert "ProductionTradingTransport|NbaVenue::production" in text
    assert "production_orders_compiled=false" in text
    assert 'test "$(uname -m)" = aarch64' in text


def test_worker_source_matches_build_gate():
    venue = (ROOT / "apps" / "nba-001" / "src" / "venue.rs").read_text(encoding="utf-8")
    assert "pub const PRODUCTION_ORDERS_COMPILED: bool = false;" in venue
    assert "const _: () = assert!(!PRODUCTION_ORDERS_COMPILED);" in venue
    for path in (ROOT / "apps" / "nba-001" / "src").glob("*.rs"):
        body = path.read_text(encoding="utf-8")
        assert "ProductionTradingTransport" not in body, path
        assert "NbaVenue::production" not in body, path


def test_deploy_refuses_live_and_guards_mlb():
    text = DEPLOY.read_text(encoding="utf-8")
    assert "live_data_only|shadow) ;;" in text
    assert "exit 78" in text
    assert "mlb_fingerprint" in text
    assert "MLB fingerprint changed" in text
    assert "rollback" in text
    assert 'binary_sha256") == sha' in text
    assert "heartbeat_at" in text
    assert "production_orders_compiled\") is False" in text
    assert "systemctl restart momento-live" not in text
    assert "systemctl stop momento-live" not in text
    assert "VITAL_AWS_CONTROL" in text.splitlines()[2]
