"""Fail-closed dataset validation. Never fill missing rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from roller.warehouse.schema import contract_for, e4_domain_ok


@dataclass
class ValidationIssue:
    code: str
    message: str
    column: str | None = None


@dataclass
class ValidationReport:
    dataset_name: str
    ok: bool
    row_count: int
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "ok": self.ok,
            "row_count": self.row_count,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def validate_frame(dataset_name: str, frame: pd.DataFrame, *, sample: int = 50_000) -> ValidationReport:
    contract = contract_for(dataset_name)
    issues: list[ValidationIssue] = []
    if contract is None:
        issues.append(ValidationIssue("UNKNOWN_DATASET", f"no contract for {dataset_name}"))
        return ValidationReport(dataset_name, False, len(frame), issues)
    missing = [c for c in contract.required_columns if c not in frame.columns]
    for col in missing:
        issues.append(ValidationIssue("MISSING_COLUMN", f"required column {col} absent", col))
    if frame.empty and not missing:
        return ValidationReport(dataset_name, True, 0, issues)
    probe = frame.head(sample)
    for col in contract.price_columns:
        if col not in probe.columns:
            continue
        bad = 0
        for value in probe[col].tolist():
            if not e4_domain_ok(value):
                bad += 1
        if bad:
            issues.append(ValidationIssue("E4_DOMAIN", f"{bad} values in {col} outside 0..10000", col))
    if "available_at" in contract.required_columns and "available_at" in probe.columns:
        empty = int((probe["available_at"].astype(str).str.strip() == "").sum())
        if empty:
            issues.append(ValidationIssue("MISSING_AVAILABLE_AT", f"{empty} empty available_at in sample"))
    ok = not any(i.code in {"MISSING_COLUMN", "E4_DOMAIN", "UNKNOWN_DATASET"} for i in issues)
    return ValidationReport(dataset_name, ok, len(frame), issues)
