"""Deterministic tennis player-name normalization for crosswalk keys.

Pure functions. No I/O, no network, no randomness. Identical input always
yields identical output.

Normalization is intentionally conservative: it removes representational noise
(unicode accents, punctuation, casing, hyphenation, whitespace) but never
guesses at identity. Anything it cannot key deterministically returns an empty
key so the caller can fail closed.
"""

from __future__ import annotations

import unicodedata
from typing import Any

# Surname particles. A trailing run of these attaches to the final token, so
# "Botic Van De Zandschulp" -> "van de zandschulp" and "Jesper De Jong" ->
# "de jong". Deliberately excludes tokens that are also real given names.
SURNAME_PARTICLES = frozenset(
    {
        "al",
        "auf",
        "bin",
        "da",
        "dal",
        "das",
        "de",
        "degli",
        "dei",
        "del",
        "della",
        "der",
        "des",
        "di",
        "do",
        "dos",
        "du",
        "el",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "op",
        "san",
        "st",
        "ten",
        "ter",
        "van",
        "vander",
        "von",
        "zu",
    }
)

_SEPARATORS = "-\u2010\u2011\u2012\u2013\u2014_'\u2019`.,/\\"


def strip_accents(raw: Any) -> str:
    """NFKD-decompose and drop combining marks. 'Rublëv' -> 'Rublev'."""
    text = str(raw or "")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_name(raw: Any) -> str:
    """Lowercase, de-accented, punctuation-free, single-spaced name."""
    text = strip_accents(raw).lower()
    buf: list[str] = []
    for ch in text:
        if ch.isalnum():
            buf.append(ch)
        elif ch in _SEPARATORS or ch.isspace():
            buf.append(" ")
        # Anything else (emoji, control chars) is dropped, not transliterated.
    return " ".join("".join(buf).split())


def name_tokens(raw: Any) -> tuple[str, ...]:
    normalized = normalize_name(raw)
    return tuple(normalized.split()) if normalized else ()


def compact(raw: Any) -> str:
    """Normalized name with all separators removed: 'van de zandschulp' ->
    'vandezandschulp'. Used so hyphenation/spacing differences between MCP and
    Kalshi cannot break an otherwise exact match."""
    return normalize_name(raw).replace(" ", "")


def full_name_key(raw: Any) -> str:
    """Order-independent full-name key.

    Tokens are sorted so 'Jesper De Jong' and 'De Jong, Jesper' key
    identically. Returns "" when there is nothing to key on, which callers
    must treat as "no key", never as a wildcard.
    """
    tokens = name_tokens(raw)
    if not tokens:
        return ""
    return "|".join(sorted(tokens))


def particle_surname(raw: Any) -> str:
    """Final token plus any immediately preceding particle run."""
    tokens = name_tokens(raw)
    if not tokens:
        return ""
    start = len(tokens) - 1
    while start > 1 and tokens[start - 1] in SURNAME_PARTICLES:
        start -= 1
    return " ".join(tokens[start:])


def surname_keys(raw: Any) -> frozenset[str]:
    """Candidate compact surname keys for one player.

    Returns a *set* because surname conventions differ between sources:
    Kalshi may render "Pattinama Kerkhove" where MCP renders the same player
    with a given name in front. A crosswalk candidate is accepted only when
    two players' key sets intersect; ambiguity is still resolved by the caller
    counting candidates, never by picking one.
    """
    tokens = name_tokens(raw)
    if not tokens:
        return frozenset()
    keys = {tokens[-1]}
    particle = particle_surname(" ".join(tokens))
    if particle:
        keys.add(particle.replace(" ", ""))
    if len(tokens) >= 2:
        keys.add((tokens[-2] + tokens[-1]))
    return frozenset(k for k in keys if k)


def pair_key(key_a: str, key_b: str) -> frozenset[str] | None:
    """Order-independent two-player key. None when either side is unkeyable or
    both sides collapse to the same key (which would make the pair ambiguous)."""
    if not key_a or not key_b or key_a == key_b:
        return None
    return frozenset({key_a, key_b})


def surname_pair_matches(
    left: tuple[frozenset[str], frozenset[str]],
    right: tuple[frozenset[str], frozenset[str]],
) -> bool:
    """True when the two unordered surname-key pairs can be aligned 1:1.

    Requires a perfect bipartite pairing, so a single shared surname is not
    enough. Both assignments are tried because player order is not stable
    across sources.
    """
    l0, l1 = left
    r0, r1 = right
    if not l0 or not l1 or not r0 or not r1:
        return False
    straight = bool(l0 & r0) and bool(l1 & r1)
    crossed = bool(l0 & r1) and bool(l1 & r0)
    return straight or crossed


def split_versus(raw: Any) -> tuple[str, str] | None:
    """Split a Kalshi-style 'Zverev vs Khachanov' title into two sides.

    Returns None unless there is exactly one separator, so three-way or
    malformed titles fail closed instead of being half-parsed.
    """
    text = str(raw or "")
    # Drop a trailing parenthetical such as " (Sep 11)".
    if "(" in text:
        text = text.split("(", 1)[0]
    lowered = strip_accents(text).lower()
    for sep in (" vs. ", " vs ", " v. ", " v "):
        if lowered.count(sep) == 1:
            idx = lowered.index(sep)
            left = text[:idx].strip()
            right = text[idx + len(sep) :].strip()
            if left and right:
                return left, right
    return None
