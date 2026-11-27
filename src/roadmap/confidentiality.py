"""RNF-Q 8: block publication when a forbidden term appears in public content.

Matching is case-insensitive, accent-insensitive (NFKD) and whole-word. Issues name only the
location where a match was found, never the term itself, because logs are public (ADR-04).
"""

from __future__ import annotations

import os
import re
import unicodedata

from roadmap.models import Issue


def normalize(text: str) -> str:
    """Casefold, fold compatibility forms and strip diacritics and invisible characters.

    "Fictício", "FICTICIO", fullwidth "ＦＩＣＴＩＣＩＯ" and "Fic​tício" (zero-width space)
    all normalize to the same string, so hidden characters cannot smuggle a term through.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(
        ch
        for ch in decomposed
        if not unicodedata.combining(ch) and unicodedata.category(ch) != "Cf"
    )
    return stripped.casefold()


def load_terms(env_var: str = "FORBIDDEN_TERMS") -> list[str]:
    """Read one term per line from an environment variable.

    Blank lines and lines starting with ``#`` are ignored. A missing variable yields ``[]``;
    the caller decides whether an empty list is acceptable.
    """
    return parse_terms(os.environ.get(env_var, ""))


def parse_terms(raw: str) -> list[str]:
    """Split a newline-separated term list, dropping blanks and ``#`` comments."""
    terms = []
    for line in raw.splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term)
    return terms


_BEFORE = r"(?<![^\W_])(?<!-)"
_AFTER = r"(?![^\W_])(?!-)"


def _compile(term: str) -> re.Pattern[str]:
    # Whole word: not preceded/followed by a word character or a joiner. Spaces, hyphens and
    # underscores inside a term are interchangeable, so "acme-corp", "acme corp" and
    # "acme_corp" all match; a false positive only blocks publication, a miss leaks.
    sep = r"[\s\-_]+"
    parts = [re.escape(p) for p in re.split(sep, normalize(term).strip()) if p]
    # Boundaries: letters/digits or a hyphen join words; "_" separates (catches "acme_corp_raw").
    return re.compile(_BEFORE + sep.join(parts) + _AFTER)


def find_forbidden(texts: list[tuple[str, str]], terms: list[str]) -> list[Issue]:
    """Return one Q8 issue per location whose text contains any forbidden term.

    ``texts`` is a list of ``(location, text)`` pairs, e.g.
    ``("projects[private-proj].description", "...")``. Locations must not carry content.
    """
    patterns = [_compile(t) for t in terms if normalize(t).strip()]
    issues: list[Issue] = []
    for location, text in texts:
        haystack = normalize(text)
        if any(p.search(haystack) for p in patterns):
            issues.append(
                Issue(
                    tab="Content",
                    row=None,
                    rule="Q8",
                    message=f"forbidden term found in {location}",
                )
            )
    return issues
