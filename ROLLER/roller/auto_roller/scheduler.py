"""launchd helpers. 00:00 verify, 02:00 ingest. Missed jobs are labeled MISSED_SCHEDULE."""

from __future__ import annotations

from pathlib import Path

from roller.config import RollerConfig
from roller.paths import momento_root

VERIFY_LABEL = "com.momento.auto-roller.verify"
INGEST_LABEL = "com.momento.auto-roller.ingest"


def launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _plist(label: str, script: Path, hour: int, log: Path, cwd: Path) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{script}</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>{hour}</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>WorkingDirectory</key>
  <string>{cwd}</string>
  <key>StandardOutPath</key>
  <string>{log}</string>
  <key>StandardErrorPath</key>
  <string>{log}</string>
</dict>
</plist>
"""


def install_plists(cfg: RollerConfig | None = None) -> dict[str, str]:
    cfg = cfg or RollerConfig()
    root = momento_root(cfg.root)
    log_dir = root / "logs" / "auto_roller"
    log_dir.mkdir(parents=True, exist_ok=True)
    agents = launch_agents_dir()
    agents.mkdir(parents=True, exist_ok=True)
    verify_script = root / "scripts" / "auto_roller_verify.sh"
    ingest_script = root / "scripts" / "auto_roller_ingest.sh"
    mapping = {
        VERIFY_LABEL: (_plist(VERIFY_LABEL, verify_script, 0, log_dir / "verify.log", cfg.root), 0),
        INGEST_LABEL: (_plist(INGEST_LABEL, ingest_script, 2, log_dir / "ingest.log", cfg.root), 2),
    }
    written: dict[str, str] = {}
    for label, (xml, _hour) in mapping.items():
        dest = agents / f"{label}.plist"
        dest.write_text(xml, encoding="utf-8")
        written[label] = str(dest)
    return written
