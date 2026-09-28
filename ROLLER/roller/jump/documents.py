"""Source-backed Jump document projections. Generated, not a second ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from roller.jump.library import repo_root
from roller.jump.research import (
    ASKED_SIX_KEY,
    PRESENT,
    UNAVAILABLE,
    JumpArtifact,
    JumpDocument,
    JumpResearchObject,
    JumpSourceReference,
)

DOC_SPECS = (
    ("overview", "Overview"),
    ("research-definition", "Research Definition"),
    ("roller-measurement", "ROLLER Measurement"),
    ("superasi-analysis", "SuperASI Analysis"),
    ("data-model", "Data Model"),
    ("methodology", "Methodology"),
    ("results", "Results"),
    ("validation", "Validation"),
    ("lineage", "Lineage"),
)


def _show(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    if value == "":
        return UNAVAILABLE
    if value == [] or value == {}:
        return UNAVAILABLE
    return str(value)


def _json_block(value: Any) -> str:
    if value in (None, "", [], {}):
        return UNAVAILABLE
    return "```json\n" + json.dumps(value, indent=2, default=str) + "\n```"


def _load_json(root: Path, rel: str) -> Any:
    path = root / rel
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _sources_md(obj: JumpResearchObject) -> str:
    lines = []
    for src in obj.sources:
        note = f" — {src.note}" if src.note else ""
        lines.append(f"- `{src.owner}` {src.role}: `{src.path}` ({src.status}){note}")
    if obj.unresolved_aliases:
        lines.append("")
        lines.append("Unresolved aliases (not merged):")
        for src in obj.unresolved_aliases:
            lines.append(f"- `{src.path}` ({src.status}) — {src.note or UNAVAILABLE}")
    return "\n".join(lines) if lines else UNAVAILABLE


def _overview(obj: JumpResearchObject) -> str:
    return "\n".join(
        [
            f"# {obj.display_name}",
            "",
            f"- Canonical key: `{obj.canonical_key}`",
            f"- Display name: {obj.display_name}",
            f"- Sports: {', '.join(obj.sports) if obj.sports else UNAVAILABLE}",
            f"- Home sport: {obj.home_sport}",
            f"- Population: {obj.population_label}",
            f"- SuperASI package_id: `{_show(obj.package_id)}`",
            f"- SuperASI folder: `{_show(obj.package_folder)}`",
            f"- research_object_id: `{_show(obj.research_object_id)}`",
            f"- UUID (metadata only): `{_show(obj.uuid)}`",
            f"- Status: {obj.status}",
            f"- Live execution: {obj.metadata.get('live_execution', False)}",
            "",
            "Jump organizes this object. ROLLER owns measurements. SuperASI owns analysis.",
            "Generated markdown is a projection, not a writable copy of W/L/EV.",
            "",
            "## Sources",
            _sources_md(obj),
        ]
    )


def _research_definition(obj: JumpResearchObject) -> str:
    pkg = obj.package or {}
    spec = pkg.get("research_spec") if isinstance(pkg.get("research_spec"), dict) else {}
    identity = spec.get("identity") if isinstance(spec.get("identity"), dict) else {}
    lines = [
        f"# Research Definition — {obj.display_name}",
        "",
        f"- Articulation: `{obj.canonical_key}`",
        f"- Identity name: {_show(identity.get('name') or obj.display_name)}",
        f"- Description: {_show(identity.get('description'))}",
        f"- Universe: {_show(spec.get('universe'))}",
        f"- Source: {_show(pkg.get('source'))}",
        f"- Price basis: {_show(pkg.get('price_basis'))}",
        "",
        "Missing fields render Unavailable. Jump does not invent a research question.",
    ]
    if obj.canonical_key == ASKED_SIX_KEY:
        lines.extend(
            [
                "",
                "## Asked-six (τ=80)",
                "",
                "FIRST80 asked-six 80→40. Population is MIXED (NBA + NCAAB + WNBA), N=1182.",
                "This folder is not the derived-four N=936 and not NBA-only 604.",
                "Choosin `#/asked-six` and `first80_asked_six.csv` are related provenance, not a second folder.",
                "Candle path ≠ fill. LIVE EXECUTION = FALSE.",
            ]
        )
    if spec:
        lines.extend(["", "## research_spec (source excerpt)", _json_block({k: spec.get(k) for k in ("schema_version", "universe", "identity", "population_binding") if k in spec})])
    return "\n".join(lines)


def _roller_measurement(obj: JumpResearchObject) -> str:
    pkg = obj.package or {}
    handoff = pkg.get("roller_handoff") if isinstance(pkg.get("roller_handoff"), dict) else {}
    lines = [
        f"# ROLLER Measurement — {obj.display_name}",
        "",
        "ROLLER is authoritative for measurements. Jump points; it does not copy the warehouse.",
        "",
    ]
    roller_sources = [src for src in obj.sources if src.owner in {"roller", "choosin"}]
    if roller_sources:
        lines.append("## Pointers")
        for src in roller_sources:
            lines.append(f"- {src.role}: `{src.path}` ({src.status})")
    else:
        lines.append(UNAVAILABLE)
    if obj.canonical_key == ASKED_SIX_KEY:
        choosin = obj.metadata.get("choosin_asked_six") if isinstance(obj.metadata.get("choosin_asked_six"), dict) else {}
        lines.extend(
            [
                "",
                "## Choosin asked-six locks (τ=80, alias hit only)",
                "",
                f"- N: {_show(choosin.get('N'))}",
                f"- cells: {_show(choosin.get('cells'))}",
                "- NBA 604 / derived-four 936 are related Choosin partitions, not this object's N.",
            ]
        )
    if handoff:
        names = []
        for row in handoff.get("measurements") or []:
            if isinstance(row, dict):
                names.append(f"{row.get('name')}={_show(row.get('status'))}")
        lines.extend(
            [
                "",
                "## SuperASI roller_handoff (copied into package, not re-measured by Jump)",
                ", ".join(names) if names else UNAVAILABLE,
                "",
                "Values below are package fields. Candle path ≠ fill. Jump does not invent EV.",
                _json_block(handoff.get("measurements")),
            ]
        )
    caveats = pkg.get("caveats") if isinstance(pkg.get("caveats"), list) else []
    if caveats:
        lines.extend(["", "## Package caveats", *[f"- {item}" for item in caveats]])
    return "\n".join(lines)


def _superasi_analysis(obj: JumpResearchObject, decomp: Any) -> str:
    pkg = obj.package or {}
    four = pkg.get("empirical_four_cell")
    lines = [
        f"# SuperASI Analysis — {obj.display_name}",
        "",
        f"- package_id: `{_show(obj.package_id)}`",
        f"- folder: `{_show(obj.package_folder)}`",
        f"- imported_at: {_show(pkg.get('imported_at'))}",
        f"- code_version: {_show(pkg.get('code_version'))}",
        f"- decomp: {'PRESENT' if decomp is not None else UNAVAILABLE}",
        "",
        "## Four-cell (package)",
        _json_block(four),
    ]
    if decomp is None:
        lines.extend(["", "## decomp.json", UNAVAILABLE])
    else:
        four_decomp = decomp.get("four_cell") if isinstance(decomp, dict) else None
        settings = decomp.get("settings") if isinstance(decomp, dict) else None
        lines.extend(
            [
                "",
                "## decomp.json settings",
                _json_block(settings),
                "",
                "## decomp.json four_cell",
                _json_block(four_decomp),
            ]
        )
        fills = decomp.get("fill_algorithms") if isinstance(decomp, dict) else None
        if isinstance(fills, dict) and "LEDGER_RULE" in fills:
            lines.extend(
                [
                    "",
                    "## LEDGER_RULE (source). L_x = barrier price. NOT A FILL.",
                    _json_block(fills.get("LEDGER_RULE")),
                ]
            )
    return "\n".join(lines)


def _data_model(obj: JumpResearchObject) -> str:
    lines = [
        f"# Data Model — {obj.display_name}",
        "",
        "Jump-native modeling files under `research/jump/` are not implemented in v1.",
        "`Data Model.md` is generated. `Models/` holds references only.",
        "",
        "Path-efficiency is a derived Data Modeling identity:",
        "ROLLER measurement + SuperASI analysis → path-efficiency object.",
        "Not executable. Not a bot. Not a live signal.",
        "",
        f"- Model status: RESEARCH_ONLY",
        f"- Writable API: not implemented",
        f"- Canonical key: `{obj.canonical_key}`",
    ]
    if obj.canonical_key == ASKED_SIX_KEY:
        lines.extend(
            [
                "",
                "Seed model reference: `path_efficiency_v0` for FIRST80 asked-six 80→40.",
                "It does not change live FIRST01 / 80/81/83/89.",
            ]
        )
    return "\n".join(lines)


def _methodology(obj: JumpResearchObject, decomp: Any) -> str:
    pkg = obj.package or {}
    settings = decomp.get("settings") if isinstance(decomp, dict) else None
    return "\n".join(
        [
            f"# Methodology — {obj.display_name}",
            "",
            f"- price_basis: {_show(pkg.get('price_basis'))}",
            f"- source: {_show(pkg.get('source'))}",
            f"- semantics_version: {_show(pkg.get('semantics_version'))}",
            f"- code_version: {_show(pkg.get('code_version'))}",
            "",
            "## Decomposition settings",
            _json_block(settings),
            "",
            "Candle path ≠ fill. Ledger price ≠ proven fill. Jump does not invent a fill algorithm.",
        ]
    )


def _results(obj: JumpResearchObject, decomp: Any) -> str:
    pkg = obj.package or {}
    seed = pkg.get("seed_locks") if isinstance(pkg.get("seed_locks"), dict) else None
    four = pkg.get("empirical_four_cell")
    lines = [
        f"# Results — {obj.display_name}",
        "",
        "Figures below are copied from SuperASI package fields. Jump does not recompute EV.",
        "Candle-path results are not fills and are not live EV.",
        "",
        f"- population_n: {_show(pkg.get('population_n'))}",
        f"- population label: {obj.population_label}",
        "",
        "## empirical_four_cell",
        _json_block(four),
        "",
        "## seed_locks",
        _json_block(seed),
    ]
    if isinstance(decomp, dict) and isinstance(decomp.get("four_cell"), dict):
        s_val = decomp["four_cell"].get("S")
        lines.extend(["", "## decomp S (source)", _json_block(s_val)])
    if four is None and seed is None:
        lines.extend(["", UNAVAILABLE])
    return "\n".join(lines)


def _validation(obj: JumpResearchObject, decomp: Any) -> str:
    pkg = obj.package or {}
    checksums = pkg.get("checksums") if isinstance(pkg.get("checksums"), dict) else None
    lines = [
        f"# Validation — {obj.display_name}",
        "",
        f"- package checksums: {_show('PRESENT' if checksums else None)}",
        "",
        _json_block(checksums),
    ]
    if obj.canonical_key == ASKED_SIX_KEY:
        choosin = obj.metadata.get("choosin_asked_six") if isinstance(obj.metadata.get("choosin_asked_six"), dict) else {}
        pkg_n = pkg.get("population_n")
        lock_n = choosin.get("N")
        match = pkg_n == lock_n if pkg_n is not None and lock_n is not None else UNAVAILABLE
        lines.extend(
            [
                "",
                "## Asked-six N identity",
                f"- package population_n: {_show(pkg_n)}",
                f"- Choosin ASKED_SIX_N_80: {_show(lock_n)}",
                f"- match: {match}",
                "- Jump does not rescan the warehouse to change N.",
            ]
        )
    if decomp is None:
        lines.extend(["", f"decomp validation: {UNAVAILABLE}"])
    return "\n".join(lines)


def _lineage(obj: JumpResearchObject) -> str:
    return "\n".join(
        [
            f"# Lineage — {obj.display_name}",
            "",
            "Authority: ROLLER measurements, SuperASI analysis, Jump organization/display/projections.",
            "Generated `.md` is rebuilt from sources on index. Not a writable second copy.",
            "",
            "## Source references",
            _sources_md(obj),
            "",
            "## Identity",
            f"- canonical_key: `{obj.canonical_key}`",
            f"- package_id: `{_show(obj.package_id)}`",
            f"- package_folder: `{_show(obj.package_folder)}`",
            f"- question_hash: `{_show(obj.question_hash)}`",
            f"- uuid: `{_show(obj.uuid)}`",
        ]
    )


def _add_doc(obj: JumpResearchObject, slug: str, title: str, body: str, provenance: list[JumpSourceReference]) -> None:
    obj.documents.append(
        JumpDocument(
            doc_id=f"doc.{obj.canonical_key}.{slug}",
            canonical_key=obj.canonical_key,
            slug=slug,
            title=title,
            body_markdown=body,
            provenance=list(provenance),
            status=PRESENT,
        )
    )


def _add_artifact(
    obj: JumpResearchObject,
    *,
    slug: str,
    name: str,
    kind: str,
    source_path: str,
    status: str,
    parent: str,
    note: str = "",
) -> None:
    obj.artifacts.append(
        JumpArtifact(
            artifact_id=f"file.{obj.canonical_key}.{slug}",
            name=name,
            kind=kind,
            source_path=source_path,
            status=status,
            canonical_key=obj.canonical_key,
            note=note,
            parent_folder=parent,
        )
    )


def attach_documents(obj: JumpResearchObject, *, root: Path | None = None) -> JumpResearchObject:
    repo = root or repo_root()
    decomp = None
    if obj.package_folder:
        decomp = _load_json(repo, f"research/superasi/library/{obj.package_folder}/decomp.json")
    provenance = list(obj.sources)
    builders = {
        "overview": lambda: _overview(obj),
        "research-definition": lambda: _research_definition(obj),
        "roller-measurement": lambda: _roller_measurement(obj),
        "superasi-analysis": lambda: _superasi_analysis(obj, decomp),
        "data-model": lambda: _data_model(obj),
        "methodology": lambda: _methodology(obj, decomp),
        "results": lambda: _results(obj, decomp),
        "validation": lambda: _validation(obj, decomp),
        "lineage": lambda: _lineage(obj),
    }
    obj.documents = []
    obj.artifacts = []
    for slug, title in DOC_SPECS:
        _add_doc(obj, slug, title, builders[slug](), provenance)

    pkg_folder = obj.package_folder
    if pkg_folder:
        base = f"research/superasi/library/{pkg_folder}"
        _add_artifact(
            obj,
            slug="package",
            name="package.json",
            kind="json",
            source_path=f"{base}/package.json",
            status=PRESENT,
            parent="source-artifacts",
            note="SuperASI package identity. Pointer, not a copy.",
        )
        trades = repo / base / "trades.json"
        if trades.is_file():
            _add_artifact(
                obj,
                slug="trades",
                name="trades.json",
                kind="json",
                source_path=f"{base}/trades.json",
                status=PRESENT,
                parent="data",
                note="Package trades pointer. Jump does not duplicate the file.",
            )
        decomp_path = repo / base / "decomp.json"
        _add_artifact(
            obj,
            slug="decomp",
            name="decomp.json",
            kind="json",
            source_path=f"{base}/decomp.json",
            status=PRESENT if decomp_path.is_file() else "MISSING",
            parent="source-artifacts",
            note="Decomposition JSON pointer." if decomp_path.is_file() else UNAVAILABLE,
        )
    if obj.canonical_key == ASKED_SIX_KEY:
        _add_artifact(
            obj,
            slug="first80-loader",
            name="first80.py",
            kind="py",
            source_path="ROLLER/roller/research/first80.py",
            status=PRESENT if (repo / "ROLLER" / "roller" / "research" / "first80.py").is_file() else "MISSING",
            parent="source-artifacts",
            note="Frozen FIRST80 loader. Do not edit.",
        )
        csv_rel = "research/first80_asked_six_chatgpt_export/first80_asked_six.csv"
        csv_path = repo / csv_rel
        if csv_path.is_file():
            _add_artifact(
                obj,
                slug="asked-six-csv",
                name="first80_asked_six.csv",
                kind="csv",
                source_path=csv_rel,
                status=PRESENT,
                parent="data",
                note="Asked-six CSV provenance pointer.",
            )
        _add_artifact(
            obj,
            slug="path-efficiency-v0",
            name="path_efficiency_v0",
            kind="model",
            source_path="research/jump/",
            status="RESEARCH_ONLY",
            parent="models",
            note="Derived path-efficiency stub. Not executable.",
        )
        from roller.jump.warehouse.registry import get_warehouse

        for sport in ("nba", "ncaab", "wnba"):
            rec = get_warehouse(sport, root=repo)
            status = "POINTER" if rec.status == "AVAILABLE" else rec.status
            _add_artifact(
                obj,
                slug=f"warehouse-{sport}",
                name=f"{sport} warehouse",
                kind="warehouse",
                source_path=rec.source_uri,
                status=status,
                parent="data",
                note="Phase 8 parquet desk. Pointer, not a copy. Confirm & Run still reads CSV.",
            )
            if rec.status != "AVAILABLE":
                continue
            for table in ("games", "markets", "observations", "settlements"):
                _add_artifact(
                    obj,
                    slug=f"warehouse-{sport}-{table}",
                    name=f"{sport}.{table}",
                    kind="table",
                    source_path=f"{rec.source_uri}/{table}",
                    status="POINTER",
                    parent="data",
                    note="Logical table pointer. used_by FIRST80_ASKED_SIX_80_40.",
                )
    return obj
