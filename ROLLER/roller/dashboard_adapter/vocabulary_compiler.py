"""Phase 3 deterministic Research Vocabulary Compiler.

Maps text → vocabulary matches + proposed research_spec.
No LLM. No empirical scan. No invented qualitative thresholds.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from roller.dashboard_adapter.research_object import REPO_DOCS
from roller.dashboard_adapter.research_object_ops import blank_research_spec
from roller.dashboard_adapter.serialize import to_jsonable

VOCABULARY_PATH = REPO_DOCS / "research_vocabulary_v0.json"
COMPILER_VERSION = "v0"

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "of",
        "and",
        "or",
        "in",
        "at",
        "on",
        "for",
        "with",
        "from",
        "by",
        "is",
        "it",
        "its",
        "as",
        "if",
        "be",
        "this",
        "that",
        "when",
        "what",
        "how",
        "time",
        "times",
        "does",
        "do",
        "did",
        "must",
        "may",
        "can",
        "vs",
        "versus",
    }
)

_AMBIGUOUS_FIELD: dict[str, tuple[str, str]] = {
    "BIG_MOVE": (
        "anchor.magnitude_e4",
        "Qualitative magnitude has no approved threshold",
    ),
    "LATE_GAME": (
        "population_binding.late_definition",
        "LATE_GAME requires an explicit definition",
    ),
    "FAVORITE": (
        "anchor.favorite_definition",
        "favorite definition must be explicit",
    ),
    "EDGE": (
        "measurement_requests",
        "EDGE is not an empirical measurement — refuse or clarify",
    ),
    "WHAT_HAPPENED_NEXT": (
        "measurement_requests",
        "WHAT_HAPPENED_NEXT requires explicit measurement_requests",
    ),
}


@lru_cache(maxsize=1)
def load_vocabulary() -> dict[str, Any]:
    """Load Phase 0 vocabulary artifact (single registry)."""
    return json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    """Deterministic normalize for matching."""
    s = text.strip().lower()
    s = s.replace("¢", " cents")
    s = s.replace("—", " ").replace("–", " ").replace("-", " ")
    s = re.sub(r"[^\w\s.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _synonym_entries(vocab: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(normalized_synonym, concept_id, concept_row) longest-first."""
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for concept in vocab.get("concepts") or []:
        cid = str(concept.get("concept") or "")
        if not cid:
            continue
        phrases = list(concept.get("synonyms") or [])
        phrases.append(cid)
        phrases.append(cid.replace("_", " "))
        for phrase in phrases:
            norm = normalize_text(str(phrase))
            if norm:
                rows.append((norm, cid, concept))
    rows.sort(key=lambda x: (-len(x[0]), x[0], x[1]))
    return rows


def _find_matches(normalized: str, vocab: dict[str, Any]) -> list[dict[str, Any]]:
    remaining = normalized
    matches: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        for a, b in occupied:
            if start < b and end > a:
                return True
        return False

    for phrase, cid, concept in _synonym_entries(vocab):
        # word-boundary-ish: allow phrase as substring with space edges
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
        for m in pattern.finditer(normalized):
            start, end = m.start(), m.end()
            if overlaps(start, end):
                continue
            occupied.append((start, end))
            remaining = remaining[:start] + (" " * (end - start)) + remaining[end:]
            is_canonical = phrase == normalize_text(cid) or phrase == normalize_text(
                cid.replace("_", " ")
            )
            matches.append(
                {
                    "phrase": m.group(0),
                    "normalized_phrase": phrase,
                    "concept_id": cid,
                    "source": "research_vocabulary_v0",
                    "confidence": "EXACT" if is_canonical else "ALIAS",
                    "_concept": concept,
                }
            )
            break  # one span per synonym pass; longest-first already

    # Deduplicate by concept_id keeping first (longest) match
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for match in matches:
        cid = match["concept_id"]
        if cid in seen:
            continue
        seen.add(cid)
        unique.append(match)
    return unique


def _parse_explicit_move(normalized: str) -> dict[str, Any] | None:
    """Parse 'down 15 cents' / 'up 10 cents' / 'dropped 15 cents'."""
    m = re.search(
        r"\b(up|down|dropped|rallied)\s+(\d{1,3})\s*cents?\b",
        normalized,
    )
    if not m:
        return None
    word = m.group(1)
    cents = int(m.group(2))
    if word in ("down", "dropped"):
        direction = "DOWN"
    else:
        direction = "UP"
    return {
        "direction": direction,
        "magnitude_e4": cents * 100,
        "phrase": m.group(0),
    }


# Deterministic compound FIRST_PRICE_TOUCH patterns (conservative).
# Require first/first-time + price context + touch/hit/reach (+ optional explicit cents).
# Do NOT match "first quarter", "first game", or bare "price 80".
_FIRST_PRICE_TOUCH_PATTERNS: list[re.Pattern[str]] = [
    # first (time) (the)? price hits/touches/reaches N
    re.compile(
        r"\bfirst(?:\s+time)?(?:\s+the)?\s+price\s+"
        r"(?:hits|hit|touches|touch|reaches|reached|reach|printed)\s+"
        r"(\d{1,2})(?:\s*cents?)?\b"
    ),
    # first price touch/hit/reach N
    re.compile(
        r"\bfirst\s+price\s+(?:touch|touches|hit|hits|reach|reaches)\s+"
        r"(\d{1,2})(?:\s*cents?)?\b"
    ),
    # (when) (the)? price first hits/touches/reaches N
    re.compile(
        r"\b(?:when\s+)?(?:the\s+)?price\s+first\s+"
        r"(?:hits|hit|touches|touch|reaches|reached|reach)\s+"
        r"(\d{1,2})(?:\s*cents?)?\b"
    ),
    # first time (it|the price) hits N
    re.compile(
        r"\bfirst\s+time(?:\s+(?:it|the\s+price))?\s+"
        r"(?:hits|hit|touches|touch|reaches|reached|reach)\s+"
        r"(\d{1,2})(?:\s*cents?)?\b"
    ),
]

# Intent without an explicit number (still FIRST_PRICE_TOUCH, price unresolved).
_FIRST_PRICE_TOUCH_INTENT: list[re.Pattern[str]] = [
    re.compile(
        r"\bfirst(?:\s+time)?(?:\s+the)?\s+price\s+"
        r"(?:hits|hit|touches|touch|reaches|reached|reach|printed)\b"
    ),
    re.compile(r"\bfirst\s+price\s+(?:touch|touches|hit|hits|reach|reaches)\b"),
    re.compile(
        r"\b(?:when\s+)?(?:the\s+)?price\s+first\s+"
        r"(?:hits|hit|touches|touch|reaches|reached|reach)\b"
    ),
]


def _detect_first_price_touch(normalized: str) -> dict[str, Any] | None:
    """Return compound FIRST_PRICE_TOUCH match with optional price_e4 and consumed phrase."""
    for pat in _FIRST_PRICE_TOUCH_PATTERNS:
        m = pat.search(normalized)
        if m:
            cents = int(m.group(1))
            return {
                "phrase": m.group(0),
                "price_e4": cents * 100,
                "span": (m.start(), m.end()),
            }
    for pat in _FIRST_PRICE_TOUCH_INTENT:
        m = pat.search(normalized)
        if m:
            return {
                "phrase": m.group(0),
                "price_e4": None,
                "span": (m.start(), m.end()),
            }
    return None


def _parse_explicit_price_e4(normalized: str, *, allow_bare: bool = False) -> int | None:
    """Parse explicit cents-style prices. Never invent qualitative prices."""
    m = re.search(r"\b(\d{1,2})\s*cents?\b", normalized)
    if m:
        return int(m.group(1)) * 100
    m = re.search(
        r"\b(?:hit|hits|touch|touches|price|at|to|reaches|reach|reached)\s+(\d{1,2})\b",
        normalized,
    )
    if m:
        return int(m.group(1)) * 100
    if allow_bare:
        m = re.search(r"\b(\d{1,2})\b", normalized)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 99:
                return n * 100
    return None


def _detect_qualitative_move(normalized: str) -> dict[str, Any] | None:
    """Detect qualitative move language without inventing magnitude.

    Synonyms like 'large move' miss 'large downward move' (non-contiguous).
    """
    if re.search(r"\b(big|large)\s+(?:\w+\s+){0,2}move\b", normalized):
        direction = None
        if re.search(r"\b(down|downward|dropped)\b", normalized):
            direction = "DOWN"
        elif re.search(r"\b(up|upward|rallied)\b", normalized):
            direction = "UP"
        return {"kind": "BIG_MOVE", "direction": direction, "phrase": "qualitative move"}
    if re.search(r"\b(downward|upward)\s+move\b", normalized):
        direction = "DOWN" if "downward" in normalized else "UP"
        return {"kind": "PRICE_MOVE", "direction": direction, "phrase": "directional move"}
    if re.search(r"\bsharply\b", normalized):
        return {"kind": "BIG_MOVE", "direction": None, "phrase": "sharply"}
    return None


def _tokens_unknown(
    normalized: str,
    matches: list[dict[str, Any]],
    consumed_phrases: list[str],
) -> list[str]:
    """Tokens not consumed by matches/patterns or stopwords / pure digits."""
    consumed = normalized
    for match in matches:
        phrase = match.get("normalized_phrase") or match.get("phrase") or ""
        if phrase:
            consumed = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", " ", consumed)
    for phrase in consumed_phrases:
        if phrase:
            consumed = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", " ", consumed)
    # Pattern residues that are not standalone concepts
    consumed = re.sub(r"\b\d{1,3}\s*cents?\b", " ", consumed)
    consumed = re.sub(
        r"\b(?:hit|hits|touch|touches|price|at|to|up|down|dropped|rallied|"
        r"move|moved|downward|large|big|first|reaches|reach|reached|printed)\b",
        " ",
        consumed,
    )
    unknown: list[str] = []
    for tok in consumed.split():
        t = tok.strip(".")
        if not t or t in _STOPWORDS:
            continue
        if t.isdigit():
            continue
        if t not in unknown:
            unknown.append(t)
    return unknown


def _ensure_anchor(spec: dict[str, Any]) -> dict[str, Any]:
    anchor = spec.get("anchor")
    if not isinstance(anchor, dict):
        anchor = {}
        spec["anchor"] = anchor
    return anchor


def _add_unresolved_param(anchor: dict[str, Any], name: str) -> None:
    params = list(anchor.get("unresolved_parameters") or [])
    if name not in params:
        params.append(name)
    anchor["unresolved_parameters"] = params


def _apply_period(spec: dict[str, Any], binds: dict[str, Any], patch: dict[str, Any]) -> None:
    field = binds.get("field")
    value = binds.get("value")
    if not field or value is None:
        return
    pop = spec.setdefault("population_binding", {})
    if not isinstance(pop, dict):
        pop = {}
        spec["population_binding"] = pop
    slices = list(pop.get("default_structural_slices") or [])
    if value not in slices:
        slices.append(value)
    pop["default_structural_slices"] = slices
    patch.setdefault("population_binding", {})["default_structural_slices"] = slices

    filters = spec.get("state_filters")
    if not isinstance(filters, dict):
        filters = {"op": "AND", "args": []}
        spec["state_filters"] = filters
    args = list(filters.get("args") or [])
    atom = {"op": "ATOM", "field": field, "operator": "eq", "value": value}
    if atom not in args:
        args.append(atom)
    filters["args"] = args
    patch["state_filters"] = filters


def _template_hint(
    matched_ids: set[str],
    anchor: dict[str, Any],
    unresolved: list[dict[str, Any]],
) -> str | None:
    price = anchor.get("price_e4")
    slices = []
    # infer from matched periods
    for cid in matched_ids:
        if cid.startswith("PERIOD_"):
            slices.append(cid.replace("PERIOD_", ""))
    if (
        "FIRST_PRICE_TOUCH" in matched_ids
        and price == 8000
        and ("Q3" in slices or "PERIOD_Q3" in matched_ids)
    ):
        return "FIRST80_Q3"
    unresolved_fields = {u["field"] for u in unresolved}
    if (
        ("PRICE_MOVE" in matched_ids or "BIG_MOVE" in matched_ids)
        and "anchor.magnitude_e4" in unresolved_fields
        and ("Q4" in slices or "PERIOD_Q4" in matched_ids)
    ):
        return "LARGE_DOWN_MOVE_Q4"
    if "BASIS" in matched_ids and (
        "OBSERVATION_TIME" in matched_ids or anchor.get("event") == "OBSERVATION_TIME"
    ):
        return "BASIS_EXTREME_AT_OBSERVATION"
    return None


def compile_research_text(
    text: str,
    base_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic vocabulary interpretation → proposed research_spec."""
    original = text or ""
    normalized = normalize_text(original)
    vocab = load_vocabulary()

    matches_raw = _find_matches(normalized, vocab) if normalized else []
    matched_ids = {m["concept_id"] for m in matches_raw}

    pattern_matches: list[dict[str, Any]] = []
    consumed_phrases: list[str] = []
    applied_bindings: list[dict[str, Any]] = []
    first_touch = _detect_first_price_touch(normalized) if normalized else None
    explicit_move = _parse_explicit_move(normalized) if normalized else None
    explicit_price = None
    if first_touch and first_touch.get("price_e4") is not None:
        explicit_price = first_touch["price_e4"]
    else:
        # Only parse standalone explicit prices when FIRST_PRICE_TOUCH already known via synonym
        # or after compound intent; do not promote bare "price 80" to FIRST_PRICE_TOUCH.
        allow_bare = "FIRST_PRICE_TOUCH" in matched_ids
        explicit_price = _parse_explicit_price_e4(normalized, allow_bare=allow_bare)

    def _ensure_match(cid: str, phrase: str, confidence: str = "PATTERN") -> None:
        matched_ids.add(cid)
        pattern_matches.append(
            {
                "phrase": phrase,
                "normalized_phrase": phrase,
                "concept_id": cid,
                "source": "compiler_pattern",
                "confidence": confidence,
            }
        )
        consumed_phrases.append(phrase)
        if not any(m["concept_id"] == cid for m in matches_raw):
            for c in vocab.get("concepts") or []:
                if c.get("concept") == cid:
                    matches_raw.append(
                        {
                            "phrase": phrase,
                            "normalized_phrase": phrase,
                            "concept_id": cid,
                            "source": "compiler_pattern",
                            "confidence": confidence,
                            "_concept": c,
                        }
                    )
                    break

    if first_touch is not None:
        _ensure_match("FIRST_PRICE_TOUCH", first_touch["phrase"])
        if first_touch.get("price_e4") is not None:
            explicit_price = first_touch["price_e4"]

    if explicit_move is not None:
        _ensure_match("PRICE_MOVE", explicit_move["phrase"])

    qualitative = _detect_qualitative_move(normalized) if normalized else None
    if qualitative is not None:
        _ensure_match(qualitative["kind"], qualitative["phrase"])
        if qualitative["kind"] == "BIG_MOVE":
            _ensure_match("PRICE_MOVE", qualitative["phrase"])

    # Vocabulary synonym "first price touch" etc. already in matched_ids — fill price if missing
    if "FIRST_PRICE_TOUCH" in matched_ids and explicit_price is None:
        explicit_price = _parse_explicit_price_e4(normalized, allow_bare=True)

    # Deduplicate matches again after patterns
    seen_cids: set[str] = set()
    matches: list[dict[str, Any]] = []
    concept_by_id: dict[str, dict[str, Any]] = {}
    for m in matches_raw:
        cid = m["concept_id"]
        concept_by_id[cid] = m.get("_concept") or concept_by_id.get(cid) or {}
        if cid in seen_cids:
            continue
        seen_cids.add(cid)
        public = {k: v for k, v in m.items() if not k.startswith("_")}
        matches.append(public)

    for pm in pattern_matches:
        if pm["concept_id"] not in seen_cids:
            matches.append(pm)
            seen_cids.add(pm["concept_id"])

    # Prefer material anchor concepts first in diagnostics
    _PRIORITY = {
        "FIRST_PRICE_TOUCH": 0,
        "PRICE_MOVE": 1,
        "OBSERVATION_TIME": 2,
        "PERIOD_Q3": 3,
        "PERIOD_Q1": 3,
        "PERIOD_Q2": 3,
        "PERIOD_Q4": 3,
    }
    matches.sort(key=lambda m: (_PRIORITY.get(m["concept_id"], 50), m["concept_id"]))

    # Fill concept rows from vocab for all matched ids
    for c in vocab.get("concepts") or []:
        cid = c.get("concept")
        if cid in matched_ids:
            concept_by_id[str(cid)] = c

    if base_spec is not None:
        spec = copy.deepcopy(base_spec)
    else:
        spec = blank_research_spec()

    patch: dict[str, Any] = {}
    unresolved: list[dict[str, Any]] = []
    warnings: list[str] = []

    # Ambiguous concepts first — never bind thresholds
    for cid in list(matched_ids):
        concept = concept_by_id.get(cid) or {}
        if concept.get("unresolved_if_ambiguous"):
            field_reason = _AMBIGUOUS_FIELD.get(cid)
            if field_reason:
                field, reason = field_reason
                source_phrase = next(
                    (m["phrase"] for m in matches if m["concept_id"] == cid),
                    cid,
                )
                unresolved.append(
                    {
                        "field": field,
                        "reason": reason,
                        "source_text": source_phrase,
                    }
                )
            options = concept.get("clarification_options") or []
            if options:
                ids = [str(o.get("id")) for o in options if o.get("id")]
                warnings.append(f"{cid} clarification_options available: {', '.join(ids)}")
            # Do not apply binds_to for ambiguous concepts

    # Bindable concepts
    for cid in list(matched_ids):
        concept = concept_by_id.get(cid) or {}
        if concept.get("unresolved_if_ambiguous"):
            continue
        binds = concept.get("binds_to")
        defaults = concept.get("default_parameters") or {}

        if cid == "FIRST_PRICE_TOUCH":
            anchor = _ensure_anchor(spec)
            anchor["event"] = "FIRST_PRICE_TOUCH"
            fields = ["anchor.event"]
            for k, v in defaults.items():
                anchor[k] = v
                fields.append(f"anchor.{k}")
            if explicit_price is not None:
                anchor["price_e4"] = explicit_price
                fields.append("anchor.price_e4")
                params = list(anchor.get("unresolved_parameters") or [])
                if "price_e4" in params:
                    params.remove("price_e4")
                anchor["unresolved_parameters"] = params
            else:
                _add_unresolved_param(anchor, "price_e4")
                unresolved.append(
                    {
                        "field": "anchor.price_e4",
                        "reason": "FIRST_PRICE_TOUCH requires explicit price_e4",
                        "source_text": original,
                    }
                )
            if isinstance(binds, dict):
                choices = binds.get("definition_version_choices") or []
                if choices:
                    warnings.append(
                        "FIRST_PRICE_TOUCH definition_version not auto-selected "
                        f"(choices: {', '.join(choices)})"
                    )
            patch["anchor"] = {k: v for k, v in anchor.items()}
            applied_bindings.append({"concept": "FIRST_PRICE_TOUCH", "fields": fields})
            continue

        if cid == "PRICE_MOVE":
            if "FIRST_PRICE_TOUCH" in matched_ids:
                continue
            anchor = _ensure_anchor(spec)
            anchor["event"] = "PRICE_MOVE"
            fields = ["anchor.event"]
            if explicit_move:
                anchor["direction"] = explicit_move["direction"]
                anchor["magnitude_e4"] = explicit_move["magnitude_e4"]
                fields.extend(["anchor.direction", "anchor.magnitude_e4"])
                params = list(anchor.get("unresolved_parameters") or [])
                for p in ("magnitude_e4", "direction"):
                    if p in params:
                        params.remove(p)
                anchor["unresolved_parameters"] = params
            else:
                if qualitative and qualitative.get("direction"):
                    anchor["direction"] = qualitative["direction"]
                    fields.append("anchor.direction")
                elif re.search(r"\b(down|downward|dropped)\b", normalized):
                    anchor["direction"] = "DOWN"
                    fields.append("anchor.direction")
                elif re.search(r"\b(up|upward|rallied)\b", normalized):
                    anchor["direction"] = "UP"
                    fields.append("anchor.direction")
                anchor["magnitude_e4"] = None
                _add_unresolved_param(anchor, "magnitude_e4")
                reason = (
                    "Qualitative magnitude has no approved threshold"
                    if "BIG_MOVE" in matched_ids
                    else "PRICE_MOVE magnitude must be explicit"
                )
                if not any(u["field"] == "anchor.magnitude_e4" for u in unresolved):
                    unresolved.append(
                        {
                            "field": "anchor.magnitude_e4",
                            "reason": reason,
                            "source_text": original,
                        }
                    )
            if defaults.get("price_field"):
                anchor["price_field"] = defaults["price_field"]
                fields.append("anchor.price_field")
            elif "price_field" not in anchor:
                anchor["price_field"] = "yes_bid_close"
                fields.append("anchor.price_field")
            patch["anchor"] = {k: v for k, v in anchor.items()}
            applied_bindings.append({"concept": "PRICE_MOVE", "fields": fields})
            continue

        if cid.startswith("PERIOD_") or cid.startswith("NCAAB_"):
            if isinstance(binds, dict) and binds.get("field"):
                _apply_period(spec, binds, patch)
                applied_bindings.append(
                    {
                        "concept": cid,
                        "fields": [
                            "population_binding.default_structural_slices",
                            "state_filters",
                        ],
                    }
                )
            continue

        if cid == "ASKED_SIX":
            pop = spec.setdefault("population_binding", {})
            if isinstance(pop, dict):
                slices = list(pop.get("default_structural_slices") or [])
                if "ASKED_SIX" not in slices:
                    slices.append("ASKED_SIX")
                pop["default_structural_slices"] = slices
                patch.setdefault("population_binding", {})["default_structural_slices"] = slices
                applied_bindings.append(
                    {
                        "concept": "ASKED_SIX",
                        "fields": ["population_binding.default_structural_slices"],
                    }
                )
            continue

        if cid == "CANDLE_1M":
            if isinstance(binds, dict) and binds.get("information_regime"):
                spec["information_regime"] = binds["information_regime"]
                patch["information_regime"] = binds["information_regime"]
                applied_bindings.append(
                    {"concept": "CANDLE_1M", "fields": ["information_regime"]}
                )
            continue

        if cid == "OBSERVABLE_PATH_ONLY":
            if isinstance(binds, dict) and binds.get("execution_interpretation"):
                spec["execution_interpretation"] = binds["execution_interpretation"]
                patch["execution_interpretation"] = binds["execution_interpretation"]
                applied_bindings.append(
                    {
                        "concept": "OBSERVABLE_PATH_ONLY",
                        "fields": ["execution_interpretation"],
                    }
                )
            continue

        if cid == "OBSERVATION_TIME":
            if "FIRST_PRICE_TOUCH" not in matched_ids and "PRICE_MOVE" not in matched_ids:
                anchor = _ensure_anchor(spec)
                anchor["event"] = "OBSERVATION_TIME"
                patch["anchor"] = {k: v for k, v in anchor.items()}
                applied_bindings.append(
                    {"concept": "OBSERVATION_TIME", "fields": ["anchor.event"]}
                )
            continue

        if cid == "STOP_T40":
            path = list(spec.get("path_conditions") or [])
            price_e4 = (defaults or {}).get("price_e4", 4000)
            binding = None
            if isinstance(binds, dict):
                binding = binds.get("definition_version")
            row = {
                "kind": "EVER_CLOSE_LE",
                "price_e4": price_e4,
                "binding": binding or "barrier_survival_v1",
            }
            path.append(row)
            spec["path_conditions"] = path
            patch["path_conditions"] = path
            applied_bindings.append({"concept": "STOP_T40", "fields": ["path_conditions"]})
            continue

        if cid == "SURVIVE":
            path = list(spec.get("path_conditions") or [])
            binding = None
            if isinstance(binds, dict):
                binding = binds.get("definition_version")
            row = {
                "kind": "NEVER_CLOSE_LE",
                "binding": binding or "barrier_survival_v1",
            }
            unresolved.append(
                {
                    "field": "path_conditions.stop_price_e4",
                    "reason": "SURVIVE requires explicit stop_price_e4",
                    "source_text": original,
                }
            )
            path.append(row)
            spec["path_conditions"] = path
            patch["path_conditions"] = path
            applied_bindings.append({"concept": "SURVIVE", "fields": ["path_conditions"]})
            continue

        if cid == "TERMINAL_YES":
            term = [{"kind": "KALSHI_YES"}]
            if isinstance(binds, dict) and binds.get("definition_version"):
                term[0]["binding"] = binds["definition_version"]
            spec["terminal_conditions"] = term
            patch["terminal_conditions"] = term
            applied_bindings.append(
                {"concept": "TERMINAL_YES", "fields": ["terminal_conditions"]}
            )
            continue

        if cid == "TERMINAL_NO":
            term = [{"kind": "KALSHI_NO"}]
            if isinstance(binds, dict) and binds.get("definition_version"):
                term[0]["binding"] = binds["definition_version"]
            spec["terminal_conditions"] = term
            patch["terminal_conditions"] = term
            applied_bindings.append(
                {"concept": "TERMINAL_NO", "fields": ["terminal_conditions"]}
            )
            continue

        if cid in (
            "BASIS",
            "RESIDUAL",
            "DELTA_MARKET",
            "GAMMA_DISCRETE",
            "THETA_OBSERVED",
            "FUNDAMENTAL_F_T",
        ):
            measurements = list(spec.get("measurement_requests") or [])
            name = cid.lower()
            binding = "UNRESOLVED"
            if isinstance(binds, dict):
                if binds.get("name"):
                    name = str(binds["name"])
                if binds.get("definition_version"):
                    binding = str(binds["definition_version"])
            measurements.append({"name": name, "binding": binding, "not_edge": True})
            spec["measurement_requests"] = measurements
            patch["measurement_requests"] = measurements
            applied_bindings.append({"concept": cid, "fields": ["measurement_requests"]})
            continue

        if cid == "CLOCK_REMAINING":
            parsers = concept.get("value_parsers") or {}
            applied = False
            for phrase, rule in parsers.items():
                if normalize_text(phrase) in normalized and isinstance(rule, dict):
                    filters = spec.get("state_filters")
                    if not isinstance(filters, dict):
                        filters = {"op": "AND", "args": []}
                        spec["state_filters"] = filters
                    args = list(filters.get("args") or [])
                    op = "lt" if rule.get("operator") == "lt" else str(rule.get("operator") or "lt")
                    args.append(
                        {
                            "op": "ATOM",
                            "field": "period_remaining_s",
                            "operator": op,
                            "value": rule.get("seconds"),
                        }
                    )
                    filters["args"] = args
                    patch["state_filters"] = filters
                    applied = True
                    break
            if not applied:
                unresolved.append(
                    {
                        "field": "state_filters.period_remaining_s",
                        "reason": "CLOCK_REMAINING requires explicit seconds",
                        "source_text": original,
                    }
                )
            continue

        if cid == "SCORE_MARGIN":
            unresolved.append(
                {
                    "field": "state_filters.score_margin",
                    "reason": "SCORE_MARGIN requires explicit value_or_range",
                    "source_text": original,
                }
            )
            continue

        if cid == "PRICE_E4":
            # unit concept; price handled via FIRST_PRICE_TOUCH / patterns
            continue

    if "BIG_MOVE" in matched_ids and "FIRST_PRICE_TOUCH" not in matched_ids:
        anchor = _ensure_anchor(spec)
        if anchor.get("event") in (None, "OBSERVATION_TIME"):
            anchor["event"] = "PRICE_MOVE"
        if re.search(r"\b(down|downward|dropped)\b", normalized):
            anchor["direction"] = "DOWN"
        elif re.search(r"\b(up|upward|rallied)\b", normalized):
            anchor["direction"] = "UP"
        anchor["magnitude_e4"] = None
        _add_unresolved_param(anchor, "magnitude_e4")
        if not any(u["field"] == "anchor.magnitude_e4" for u in unresolved):
            unresolved.append(
                {
                    "field": "anchor.magnitude_e4",
                    "reason": "Qualitative magnitude has no approved threshold",
                    "source_text": original,
                }
            )
        patch["anchor"] = {k: v for k, v in anchor.items()}
        if not any(b["concept"] == "PRICE_MOVE" for b in applied_bindings):
            applied_bindings.append(
                {
                    "concept": "PRICE_MOVE",
                    "fields": ["anchor.event", "anchor.magnitude_e4"],
                }
            )

    unknown_terms = (
        _tokens_unknown(normalized, matches, consumed_phrases) if normalized else []
    )

    # Material bindings exclude unit-only PRICE_E4 (never a standalone applied concept).
    material_concepts = {b["concept"] for b in applied_bindings}

    missing_required = False
    for cid in matched_ids:
        concept = concept_by_id.get(cid) or {}
        if concept.get("unresolved_if_ambiguous"):
            continue
        if cid == "PRICE_E4":
            continue
        for req in concept.get("required_parameters") or []:
            if cid == "FIRST_PRICE_TOUCH" and req == "price_e4":
                if not (_ensure_anchor(spec).get("price_e4")):
                    missing_required = True
            if cid == "PRICE_MOVE" and req == "magnitude_e4":
                if _ensure_anchor(spec).get("magnitude_e4") is None:
                    missing_required = True
            if cid == "PRICE_MOVE" and req == "direction":
                if not _ensure_anchor(spec).get("direction"):
                    missing_required = True

    # Status depends on compiler-applied bindings — never on blank_spec defaults alone.
    unit_only = matched_ids <= {"PRICE_E4"} or matched_ids == set()
    if not matches and not matched_ids:
        status = "NO_MATCH"
    elif not material_concepts and unresolved:
        status = "UNRESOLVED"
    elif not material_concepts and matches:
        # e.g. only PRICE_E4 recognized — not RESOLVED via OBSERVATION_TIME blank default
        status = "PARTIAL" if matched_ids - {"PRICE_E4"} or unknown_terms else "NO_MATCH"
        if matched_ids == {"PRICE_E4"}:
            status = "PARTIAL"
            warnings.append(
                "PRICE_E4 recognized without an anchor event binding "
                "(blank OBSERVATION_TIME is not a compiler-derived anchor)"
            )
    elif unresolved or missing_required:
        status = "PARTIAL"
    elif material_concepts:
        status = "RESOLVED"
    else:
        status = "NO_MATCH"

    if unit_only and status == "RESOLVED":
        status = "PARTIAL"

    hint = _template_hint(matched_ids, _ensure_anchor(spec), unresolved)

    # Identity description from input (non-authoritative label only)
    identity = spec.setdefault("identity", {})
    if isinstance(identity, dict) and original.strip():
        if not identity.get("description"):
            identity["description"] = f"Compiled from: {original.strip()}"
            patch.setdefault("identity", {})["description"] = identity["description"]

    return to_jsonable(
        {
            "status": status,
            "input": original,
            "matches": matches,
            "proposed_patch": patch,
            "proposed_spec": spec,
            "unresolved": unresolved,
            "unknown_terms": unknown_terms,
            "warnings": warnings,
            "template_hint": hint,
            "applied_bindings": applied_bindings,
            "compiler_version": COMPILER_VERSION,
        }
    )


__all__ = [
    "COMPILER_VERSION",
    "VOCABULARY_PATH",
    "compile_research_text",
    "load_vocabulary",
    "normalize_text",
]
