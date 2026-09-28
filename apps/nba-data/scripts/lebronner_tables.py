#!/usr/bin/env python3
"""Lossless FIRST75 / FIRST80 tables for the Lebronner archive.

Reads the locked terminal-path decomp summary. Does not rescan the tape.
Does not change live FIRST01. n is trigger events, not Kalshi trade prints.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

REPO = Path("/Users/user/Desktop/Momento")
DECOMP_SUMMARY = REPO / "research" / "first75_terminal_path_decomp" / "summary.json"

SPORT_LABEL = {
    "wnba": "WNBA",
    "nba": "NBA",
    "ncaab_p5": "NCAAB P5",
}

SLICE_LABEL = {
    "Q2": "2Q",
    "Q3": "3Q",
    "Q2∪Q3": "2Q∪3Q",
    "H1_2": "1H second 10",
    "H2_1": "2H first 10",
    "H1_2∪H2_1": "1H2 ∪ 2H1",
}

ASKED_SIX = (
    ("wnba", "Q2"),
    ("wnba", "Q3"),
    ("nba", "Q2"),
    ("nba", "Q3"),
    ("ncaab_p5", "H1_2"),
    ("ncaab_p5", "H2_1"),
)

UNION_SLICES = {
    ("wnba", "Q2∪Q3"),
    ("nba", "Q2∪Q3"),
    ("ncaab_p5", "H1_2∪H2_1"),
}

OBJECTS = (
    ("p", "terminal", "P(W | FIRST_q)"),
    ("alpha", "terminal", "P(W) − K"),
    ("s_W", "winner_path", "P(¬T40 | W)"),
    ("s_L", "loser_path", "P(¬T40 | L)"),
    ("joint", "joint_win_survive", "P(W ∩ ¬T40)"),
    ("S", "unconditional_barrier", "P(¬T40)"),
)


def load_decomp() -> dict:
    if not DECOMP_SUMMARY.exists():
        raise FileNotFoundError(f"locked decomp missing: {DECOMP_SUMMARY}")
    return json.loads(DECOMP_SUMMARY.read_text())


def _ci(pair) -> str:
    if not pair or pair[0] is None or pair[1] is None:
        return "—"
    return f"{pair[0]}–{pair[1]}"


def _pct(x: float | None, digits: int = 4) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}%"


def _pp(x: float | None, digits: int = 4) -> str:
    if x is None:
        return "—"
    return f"{x:+.{digits}f}"


def flatten_decomp(sport: str, slice_key: str, role: str, d: dict) -> dict:
    term = d["terminal"]
    vs = term.get("vs_null") or {}
    cells = d["cells"]
    k = d["quote_k"]
    return {
        "sport": sport,
        "sport_label": SPORT_LABEL[sport],
        "slice": slice_key,
        "slice_label": SLICE_LABEL.get(slice_key, slice_key),
        "role": role,
        "rule": d["label"],
        "K": k,
        "n": d["n"],
        "W": d["N_W"],
        "L": d["N_L"],
        "W_and_not_T40": cells["W_and_not_T40"],
        "W_and_T40": cells["W_and_T40"],
        "L_and_not_T40": cells["L_and_not_T40"],
        "L_and_T40": cells["L_and_T40"],
        "p": term["estimate"],
        "p_pct": term["pct"],
        "p_wilson": term["wilson_ci95"],
        "p_cp": term["clopper_pearson_ci95"],
        "alpha": term["alpha_terminal"],
        "alpha_pp": term["alpha_pct_points"],
        "alpha_wilson": term["alpha_wilson_ci95"],
        "wilson_excludes_k": term["wilson_excludes_k"],
        "p_two_sided": vs.get("p_two_sided"),
        "p_greater": vs.get("p_one_sided_greater"),
        "p_less": vs.get("p_one_sided_less"),
        "s_W": d["winner_path"]["estimate"],
        "s_W_pct": d["winner_path"]["pct"],
        "s_W_n": d["winner_path"]["n"],
        "s_W_k": d["winner_path"]["k"],
        "s_W_wilson": d["winner_path"]["wilson_ci95"],
        "s_W_cp": d["winner_path"]["clopper_pearson_ci95"],
        "s_L": d["loser_path"]["estimate"],
        "s_L_pct": d["loser_path"]["pct"],
        "s_L_n": d["loser_path"]["n"],
        "s_L_k": d["loser_path"]["k"],
        "s_L_wilson": d["loser_path"]["wilson_ci95"],
        "s_L_cp": d["loser_path"]["clopper_pearson_ci95"],
        "joint": d["joint_win_survive"]["estimate"],
        "joint_pct": d["joint_win_survive"]["pct"],
        "joint_k": d["joint_win_survive"]["k"],
        "joint_wilson": d["joint_win_survive"]["wilson_ci95"],
        "joint_cp": d["joint_win_survive"]["clopper_pearson_ci95"],
        "S": d["unconditional_barrier"]["estimate"],
        "S_pct": d["unconditional_barrier"]["pct"],
        "S_k": d["unconditional_barrier"]["k"],
        "S_wilson": d["unconditional_barrier"]["wilson_ci95"],
        "S_cp": d["unconditional_barrier"]["clopper_pearson_ci95"],
        "p_times_s_W": d["reconstruction"]["p_times_s_W"],
        "identity_ok": d["reconstruction"]["identity_p_times_s_W_equals_joint"],
    }


def collect_rows(summary: dict) -> list[dict]:
    rows = []
    for sport, block in summary["sports"].items():
        rows.append(
            flatten_decomp(sport, "FULL", "full_sport", block["decomp_FIRST75_full"])
        )
        rows.append(
            flatten_decomp(sport, "FULL", "full_sport", block["decomp_FIRST80_full"])
        )
        for sl, rec in block["slices"].items():
            role = "derived_union" if (sport, sl) in UNION_SLICES else "asked_slice"
            if (sport, sl) in ASKED_SIX:
                role = "asked_six"
            rows.append(flatten_decomp(sport, sl, role, rec["decomp_FIRST75"]))
            rows.append(flatten_decomp(sport, sl, role, rec["decomp_FIRST80"]))
    return rows


def universe_inventory(summary: dict) -> list[dict]:
    out = []
    for sport, block in summary["sports"].items():
        d75 = block["decomp_FIRST75_full"]
        d80 = block["decomp_FIRST80_full"]
        p75 = sum(block["FIRST75_partition"].values())
        p80 = sum(block["FIRST80_partition"].values())
        if p75 != d75["n"]:
            raise RuntimeError(f"HALT {sport} FIRST75 partition {p75} != {d75['n']}")
        if p80 != d80["n"]:
            raise RuntimeError(f"HALT {sport} FIRST80 partition {p80} != {d80['n']}")
        out.append(
            {
                "sport": sport,
                "sport_label": SPORT_LABEL[sport],
                "label": block.get("label"),
                "FIRST75_n": d75["n"],
                "FIRST75_W": d75["N_W"],
                "FIRST75_L": d75["N_L"],
                "FIRST80_n": d80["n"],
                "FIRST80_W": d80["N_W"],
                "FIRST80_L": d80["N_L"],
                "FIRST75_partition": block["FIRST75_partition"],
                "FIRST80_partition": block["FIRST80_partition"],
                "note": "n = settled FIRST_q trigger events, one per event. Not Kalshi prints.",
            }
        )
    return out


def _values(rows: list[dict], key: str) -> list[float]:
    return [float(r[key]) for r in rows if r[key] is not None]


def _quantiles(xs: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return None, None
    qs = statistics.quantiles(xs, n=4, method="inclusive")
    return qs[0], qs[2]


def slice_distribution(asked: list[dict], object_key: str, pct_key: str) -> dict:
    xs = _values(asked, object_key)
    pcts = _values(asked, pct_key)
    q1, q3 = _quantiles(pcts)
    return {
        "n_slices": len(xs),
        "unweighted_mean": None if not xs else statistics.mean(xs),
        "unweighted_mean_pct": None if not pcts else statistics.mean(pcts),
        "median": None if not xs else statistics.median(xs),
        "median_pct": None if not pcts else statistics.median(pcts),
        "min": None if not xs else min(xs),
        "min_pct": None if not pcts else min(pcts),
        "max": None if not xs else max(xs),
        "max_pct": None if not pcts else max(pcts),
        "range_pp": None if not pcts else max(pcts) - min(pcts),
        "q1_pct": q1,
        "q3_pct": q3,
        "iqr_pp": None if q1 is None or q3 is None else q3 - q1,
        "slice_values_pct": pcts,
        "weighting_note": "Unweighted across the six asked rows. Not the event-weighted pool.",
    }


def asked_rows(rows: list[dict], rule: str) -> list[dict]:
    want = [r for r in rows if r["role"] == "asked_six" and r["rule"] == rule]
    order = {pair: i for i, pair in enumerate(ASKED_SIX)}
    want.sort(key=lambda r: order[(r["sport"], r["slice"])])
    return want


def build_table_doc(summary: dict) -> dict:
    rows = collect_rows(summary)
    inventory = universe_inventory(summary)
    a75 = asked_rows(rows, "FIRST75")
    a80 = asked_rows(rows, "FIRST80")
    if len(a75) != 6 or len(a80) != 6:
        raise RuntimeError(f"HALT asked six: 75={len(a75)} 80={len(a80)}")
    if sum(r["n"] for r in a75) != 1126:
        raise RuntimeError("HALT asked FIRST75 n")
    if sum(r["n"] for r in a80) != 1182:
        raise RuntimeError("HALT asked FIRST80 n")

    p75 = summary["pooled_six_decomp"]["FIRST75"]
    p80 = summary["pooled_six_decomp"]["FIRST80"]

    def dist_block(asked: list[dict], pooled: dict, rule: str) -> dict:
        out = {}
        for name, src, obj in OBJECTS:
            if name == "alpha":
                xs = _values(asked, "alpha_pp")
                q1, q3 = _quantiles(xs)
                out[name] = {
                    "object": obj,
                    "n_slices": 6,
                    "unweighted_mean_pp": statistics.mean(xs),
                    "median_pp": statistics.median(xs),
                    "min_pp": min(xs),
                    "max_pp": max(xs),
                    "range_pp": max(xs) - min(xs),
                    "q1_pp": q1,
                    "q3_pp": q3,
                    "iqr_pp": None if q1 is None else q3 - q1,
                    "event_weighted_alpha": pooled["terminal"]["alpha_terminal"],
                    "event_weighted_alpha_pp": pooled["terminal"]["alpha_pct_points"],
                    "pooled_wilson": pooled["terminal"]["alpha_wilson_ci95"],
                    "pooled_p_wilson": pooled["terminal"]["wilson_ci95"],
                    "wilson_excludes_k": pooled["terminal"]["wilson_excludes_k"],
                    "slice_values_pp": xs,
                }
            else:
                key = {"p": "p", "s_W": "s_W", "s_L": "s_L", "joint": "joint", "S": "S"}[name]
                pct_key = f"{key}_pct"
                block = slice_distribution(asked, key, pct_key)
                src_d = pooled[src]
                block["object"] = obj
                block["event_weighted"] = src_d["estimate"]
                block["event_weighted_pct"] = src_d["pct"]
                block["event_weighted_k"] = src_d["k"]
                block["event_weighted_n"] = src_d["n"]
                block["pooled_wilson"] = src_d["wilson_ci95"]
                block["pooled_cp"] = src_d["clopper_pearson_ci95"]
                out[name] = block
        return {"rule": rule, "objects": out}

    return {
        "source": str(DECOMP_SUMMARY.relative_to(REPO)),
        "unit": "FIRST_q trigger events (one per settled event). Not Kalshi trade prints.",
        "inventory": inventory,
        "universe_totals": {
            "FIRST75_full_sum_three_sports": sum(x["FIRST75_n"] for x in inventory),
            "FIRST80_full_sum_three_sports": sum(x["FIRST80_n"] for x in inventory),
            "asked_six_FIRST75": 1126,
            "asked_six_FIRST80": 1182,
            "note": "Full-sport sums include Q1/Q4/H1_1/H2_2/OT/UNALIGNED. Asked six do not.",
        },
        "rows": rows,
        "asked_six_FIRST75_n": sum(r["n"] for r in a75),
        "asked_six_FIRST80_n": sum(r["n"] for r in a80),
        "distributions": {
            "FIRST75_asked_six": dist_block(a75, p75, "FIRST75"),
            "FIRST80_asked_six": dist_block(a80, p80, "FIRST80"),
        },
        "pooled": {
            "FIRST75": {
                "n": p75["n"],
                "cells": p75["cells"],
                "terminal": p75["terminal"],
                "winner_path": p75["winner_path"],
                "loser_path": p75["loser_path"],
                "joint": p75["joint_win_survive"],
                "S": p75["unconditional_barrier"],
            },
            "FIRST80": {
                "n": p80["n"],
                "cells": p80["cells"],
                "terminal": p80["terminal"],
                "winner_path": p80["winner_path"],
                "loser_path": p80["loser_path"],
                "joint": p80["joint_win_survive"],
                "S": p80["unconditional_barrier"],
            },
        },
    }


def _row_compact(r: dict) -> str:
    vs = "excludes K" if r["wilson_excludes_k"] else "includes K"
    return (
        f"| {r['sport_label']} | {r['slice_label']} | {r['n']} | {r['W']} | "
        f"{r['W_and_not_T40']} | {_pct(r['p_pct'])} | {_ci(r['p_wilson'])} | "
        f"{_pp(r['alpha_pp'], 2)} | {_ci(r['alpha_wilson'])} | "
        f"{_pct(r['s_W_pct'])} | {_ci(r['s_W_wilson'])} | "
        f"{_pct(r['s_L_pct'])} | {_ci(r['s_L_wilson'])} | "
        f"{r['W_and_not_T40']} | {_pct(r['joint_pct'])} | {_ci(r['joint_wilson'])} | "
        f"{_pct(r['S_pct'])} | {_ci(r['S_wilson'])} | {vs} |"
    )


def _row_full(r: dict) -> str:
    vs = "excludes K" if r["wilson_excludes_k"] else "includes K"
    p2 = "—" if r["p_two_sided"] is None else f"{r['p_two_sided']:.5g}"
    return (
        f"| {r['sport_label']} | {r['slice_label']} | {r['rule']} | {r['role']} | "
        f"{r['n']} | {r['W']} | {r['L']} | "
        f"{r['W_and_not_T40']} | {r['W_and_T40']} | {r['L_and_not_T40']} | {r['L_and_T40']} | "
        f"{r['W']}/{r['n']} | {_pct(r['p_pct'])} | {_ci(r['p_wilson'])} | {_ci(r['p_cp'])} | "
        f"{_pp(r['alpha_pp'])} | {_ci(r['alpha_wilson'])} | {p2} | {vs} | "
        f"{r['s_W_k']}/{r['s_W_n']} | {_pct(r['s_W_pct'])} | {_ci(r['s_W_wilson'])} | {_ci(r['s_W_cp'])} | "
        f"{r['s_L_k']}/{r['s_L_n']} | {_pct(r['s_L_pct'])} | {_ci(r['s_L_wilson'])} | {_ci(r['s_L_cp'])} | "
        f"{r['joint_k']}/{r['n']} | {_pct(r['joint_pct'])} | {_ci(r['joint_wilson'])} | {_ci(r['joint_cp'])} | "
        f"{r['S_k']}/{r['n']} | {_pct(r['S_pct'])} | {_ci(r['S_wilson'])} | {_ci(r['S_cp'])} |"
    )


COMPACT_HEADER = (
    "| Sport | Slice | N | W | W∩¬T40 | p | p Wilson | α | α Wilson | "
    "s_W | s_W Wilson | s_L | s_L Wilson | W∩¬T40 | joint | joint Wilson | "
    "S | S Wilson | CI vs K |"
)
COMPACT_ALIGN = "|---|---|---:|---:|---:|---:|---|---:|---|---:|---|---:|---|---:|---:|---|---:|---|---|"

FULL_HEADER = (
    "| Sport | Slice | Rule | Role | N | W | L | W∩¬T40 | W∩T40 | L∩¬T40 | L∩T40 | "
    "W/N | p | p Wilson | p CP | α (pp) | α Wilson | two-sided p | CI vs K | "
    "¬T40∩W / W | s_W | s_W Wilson | s_W CP | ¬T40∩L / L | s_L | s_L Wilson | s_L CP | "
    "W∩¬T40 / N | joint | joint Wilson | joint CP | ¬T40 / N | S | S Wilson | S CP |"
)
FULL_ALIGN = "|" + "|".join(["---"] * 35) + "|"


def _dist_table(block: dict) -> list[str]:
    lines = [
        "| Object | Unweighted mean | Median | Min | Max | Range | Q1 | Q3 | IQR | "
        "Event-weighted (k/N) | Pooled Wilson | Pooled CP |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    objs = block["objects"]
    for name, src, obj in OBJECTS:
        rec = objs[name]
        if name == "alpha":
            lines.append(
                f"| {obj} | {_pp(rec['unweighted_mean_pp'], 4)} | {_pp(rec['median_pp'], 4)} | "
                f"{_pp(rec['min_pp'], 4)} | {_pp(rec['max_pp'], 4)} | {rec['range_pp']:.4f} | "
                f"{_pp(rec['q1_pp'], 4)} | {_pp(rec['q3_pp'], 4)} | {rec['iqr_pp']:.4f} | "
                f"{_pp(rec['event_weighted_alpha_pp'], 4)} | {_ci(rec['pooled_wilson'])} | — |"
            )
        else:
            ew = f"{rec['event_weighted_pct']}% ({rec['event_weighted_k']}/{rec['event_weighted_n']})"
            lines.append(
                f"| {obj} | {_pct(rec['unweighted_mean_pct'])} | {_pct(rec['median_pct'])} | "
                f"{_pct(rec['min_pct'])} | {_pct(rec['max_pct'])} | {rec['range_pp']:.4f} pp | "
                f"{_pct(rec['q1_pct'])} | {_pct(rec['q3_pct'])} | {rec['iqr_pp']:.4f} pp | "
                f"{ew} | {_ci(rec['pooled_wilson'])} | {_ci(rec['pooled_cp'])} |"
            )
    return lines


def render_markdown(doc: dict) -> str:
    inv = doc["inventory"]
    tot = doc["universe_totals"]
    rows = doc["rows"]
    a75 = asked_rows(rows, "FIRST75")
    a80 = asked_rows(rows, "FIRST80")
    full75 = [r for r in rows if r["role"] == "full_sport" and r["rule"] == "FIRST75"]
    full80 = [r for r in rows if r["role"] == "full_sport" and r["rule"] == "FIRST80"]
    unions75 = [r for r in rows if r["role"] == "derived_union" and r["rule"] == "FIRST75"]
    unions80 = [r for r in rows if r["role"] == "derived_union" and r["rule"] == "FIRST80"]

    lines = [
        "# Lebronner lossless tables",
        "",
        "FIRST75 and FIRST80 terminal × path rates with Wilson and Clopper–Pearson",
        "intervals, universe event counts, and slice mean / median / IQR.",
        "",
        "```",
        "LIVE EXECUTION = FALSE",
        "CANDLE PATH ≠ ACTUAL FILL",
        "OBSERVED CALIBRATION DEVIATION ≠ PROVEN MARKET INEFFICIENCY",
        "```",
        "",
        f"Source: `{doc['source']}`. Reconstructs; does not rescan.",
        "**n is FIRST_q trigger events** (one per settled event), not Kalshi trade prints.",
        "Unions are derived and are **not** added into the asked-six pool.",
        "UNALIGNED prints are in the full-sport universe and out of the asked slices.",
        "",
        "## 1. Universe event counts",
        "",
        "| Sport | Warehouse | FIRST75 N | FIRST75 W | FIRST75 L | FIRST80 N | FIRST80 W | FIRST80 L |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for x in inv:
        lines.append(
            f"| {x['sport_label']} | {x['label']} | **{x['FIRST75_n']}** | {x['FIRST75_W']} | "
            f"{x['FIRST75_L']} | **{x['FIRST80_n']}** | {x['FIRST80_W']} | {x['FIRST80_L']} |"
        )
    lines.extend(
        [
            f"| **sum three sports** | full warehouses | **{tot['FIRST75_full_sum_three_sports']}** | "
            f"— | — | **{tot['FIRST80_full_sum_three_sports']}** | — | — |",
            f"| **asked six** | 2Q+3Q / H1_2+H2_1 only | **{tot['asked_six_FIRST75']}** | "
            f"871 | 255 | **{tot['asked_six_FIRST80']}** | 991 | 191 |",
            "",
            "Asked-six FIRST80 W = 883+108 = 991. Do not add FIRST75 N to FIRST80 N.",
            "",
            "### Clock-bin partitions (every trigger, including bins not in the asked six)",
            "",
        ]
    )
    for x in inv:
        lines.append(f"**{x['sport_label']} FIRST75**")
        lines.append("")
        keys = sorted(x["FIRST75_partition"])
        lines.append("| " + " | ".join(keys) + " | sum |")
        lines.append("|" + "|".join(["---:"] * (len(keys) + 1)) + "|")
        vals = [x["FIRST75_partition"][k] for k in keys]
        lines.append("| " + " | ".join(str(v) for v in vals) + f" | {sum(vals)} |")
        lines.append("")
        lines.append(f"**{x['sport_label']} FIRST80**")
        lines.append("")
        keys = sorted(x["FIRST80_partition"])
        lines.append("| " + " | ".join(keys) + " | sum |")
        lines.append("|" + "|".join(["---:"] * (len(keys) + 1)) + "|")
        vals = [x["FIRST80_partition"][k] for k in keys]
        lines.append("| " + " | ".join(str(v) for v in vals) + f" | {sum(vals)} |")
        lines.append("")

    lines.extend(
        [
            "Partition sums must equal the full-sport N. UNALIGNED is excluded from slices.",
            "",
            "## 2. Asked six — FIRST75 (user table + all Wilson intervals)",
            "",
            "K = 0.75. One observation per FIRST75 event.",
            "",
            COMPACT_HEADER,
            COMPACT_ALIGN,
        ]
    )
    for r in a75:
        lines.append(_row_compact(r))
    p75 = doc["pooled"]["FIRST75"]
    lines.append(
        f"| **pooled six** | asked rows | **{p75['n']}** | **{p75['terminal']['k']}** | "
        f"**{p75['cells']['W_and_not_T40']}** | **{_pct(p75['terminal']['pct'])}** | "
        f"{_ci(p75['terminal']['wilson_ci95'])} | **{_pp(p75['terminal']['alpha_pct_points'], 2)}** | "
        f"{_ci(p75['terminal']['alpha_wilson_ci95'])} | **{_pct(p75['winner_path']['pct'])}** | "
        f"{_ci(p75['winner_path']['wilson_ci95'])} | **{_pct(p75['loser_path']['pct'])}** | "
        f"{_ci(p75['loser_path']['wilson_ci95'])} | **{p75['cells']['W_and_not_T40']}** | "
        f"**{_pct(p75['joint']['pct'])}** | {_ci(p75['joint']['wilson_ci95'])} | "
        f"**{_pct(p75['S']['pct'])}** | {_ci(p75['S']['wilson_ci95'])} | "
        f"{'excludes K' if p75['terminal']['wilson_excludes_k'] else 'includes K'} |"
    )

    lines.extend(
        [
            "",
            "## 3. Asked six — FIRST80 (same clock slices, not retuned)",
            "",
            "K = 0.80. α₈₀ = p − 0.80. Same slice definitions as FIRST75; different τ.",
            "",
            COMPACT_HEADER,
            COMPACT_ALIGN,
        ]
    )
    for r in a80:
        lines.append(_row_compact(r))
    p80 = doc["pooled"]["FIRST80"]
    lines.append(
        f"| **pooled six** | asked rows | **{p80['n']}** | **{p80['terminal']['k']}** | "
        f"**{p80['cells']['W_and_not_T40']}** | **{_pct(p80['terminal']['pct'])}** | "
        f"{_ci(p80['terminal']['wilson_ci95'])} | **{_pp(p80['terminal']['alpha_pct_points'], 2)}** | "
        f"{_ci(p80['terminal']['alpha_wilson_ci95'])} | **{_pct(p80['winner_path']['pct'])}** | "
        f"{_ci(p80['winner_path']['wilson_ci95'])} | **{_pct(p80['loser_path']['pct'])}** | "
        f"{_ci(p80['loser_path']['wilson_ci95'])} | **{p80['cells']['W_and_not_T40']}** | "
        f"**{_pct(p80['joint']['pct'])}** | {_ci(p80['joint']['wilson_ci95'])} | "
        f"**{_pct(p80['S']['pct'])}** | {_ci(p80['S']['wilson_ci95'])} | "
        f"{'excludes K' if p80['terminal']['wilson_excludes_k'] else 'includes K'} |"
    )

    lines.extend(
        [
            "",
            "## 4. Mean / median / IQR vs event-weighted pool",
            "",
            "Unweighted statistics treat each of the six asked rows as one point.",
            "The scientific pool is **one observation per trigger** (k/N).",
            "Those two numbers are different objects. Intervals on the pool are",
            "Wilson / Clopper–Pearson. Min / max / IQR are the spread of the six",
            "point estimates, not a new binomial interval.",
            "",
            "### FIRST75 asked six",
            "",
        ]
    )
    lines.extend(_dist_table(doc["distributions"]["FIRST75_asked_six"]))
    lines.extend(
        [
            "",
            "### FIRST80 asked six",
            "",
        ]
    )
    lines.extend(_dist_table(doc["distributions"]["FIRST80_asked_six"]))

    lines.extend(
        [
            "",
            "## 5. Full-sport universes (all clock bins)",
            "",
            "Includes Q1 / Q4 / H1_1 / H2_2 / OT / UNALIGNED. Not the asked six.",
            "",
            "### FIRST75",
            "",
            COMPACT_HEADER,
            COMPACT_ALIGN,
        ]
    )
    for r in full75:
        lines.append(_row_compact(r))
    lines.extend(["", "### FIRST80", "", COMPACT_HEADER, COMPACT_ALIGN])
    for r in full80:
        lines.append(_row_compact(r))

    lines.extend(
        [
            "",
            "## 6. Derived unions (not added to the asked-six pool)",
            "",
            COMPACT_HEADER,
            COMPACT_ALIGN,
        ]
    )
    for r in unions75 + unions80:
        lines.append(_row_compact(r))

    lines.extend(
        [
            "",
            "## 7. Lossless wide table (every row, both rules)",
            "",
            "k/n integers are the authority. Percents and intervals are derived.",
            "",
            FULL_HEADER,
            FULL_ALIGN,
        ]
    )
    order_role = {"asked_six": 0, "derived_union": 1, "full_sport": 2}
    ordered = sorted(
        rows,
        key=lambda r: (
            r["rule"],
            order_role.get(r["role"], 9),
            r["sport"],
            r["slice"],
        ),
    )
    for r in ordered:
        lines.append(_row_full(r))

    lines.extend(
        [
            "",
            "## 8. What this is not",
            "",
            "- Not Kalshi trade-print counts.",
            "- Not fills, fees, or live P&L.",
            "- Not a claim that any slice is a tradable filter.",
            "- Unweighted mean ≠ event-weighted pool.",
            "- FIRST75 T40 and FIRST80 T40 use different timestamps.",
            "",
            "**LIVE DEPLOYMENT: NOT AUTHORIZED**",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_tables(dests: list[Path]) -> dict:
    summary = load_decomp()
    doc = build_table_doc(summary)
    text = render_markdown(doc)
    payload = json.dumps(doc, indent=2) + "\n"
    for dest in dests:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "TABLES.md").write_text(text)
        (dest / "tables.json").write_text(payload)
    return doc
