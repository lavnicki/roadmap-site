"""Labelled eval suite for the leak scanner (``roadmap eval-leaks``).

Each case is scanned exactly like a published file and must be blocked or allowed as labelled.
Fake secrets are written as ``parts`` and joined at run time, so the repository itself never
contains a string that looks like a real credential (``roadmap audit-repo`` stays clean).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from roadmap.leakscan import Guardrails, load_guardrails, scan_document


@dataclass(frozen=True)
class LeakCase:
    id: str
    category: str
    kind: str  # "html" or "text"
    content: str
    expect: str  # "block" or "allow"
    why: str


@dataclass
class EvalResult:
    total: int = 0
    tp: int = 0  # blocked, should block
    tn: int = 0  # allowed, should allow
    fp: int = 0  # blocked, should allow
    fn: int = 0  # allowed, should block (a leak)
    by_category: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))
    failures: list[str] = field(default_factory=list)

    def summary(self) -> str:
        recall = self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0
        precision = self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0
        lines = [
            f"leak evals: {self.total} cases, {self.total - len(self.failures)} passed",
            f"recall (leaks caught) {recall:.1%} | precision {precision:.1%} | "
            f"missed leaks {self.fn} | false alarms {self.fp}",
            "by category:",
        ]
        for cat in sorted(self.by_category):
            ok, n = self.by_category[cat]
            lines.append(f"  {cat:<16} {ok}/{n}")
        return "\n".join(lines)


def load_cases(path: Path) -> tuple[list[str], list[str], list[LeakCase]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases = []
    for raw in data["cases"]:
        content = raw["content"] if "content" in raw else "".join(raw["parts"])
        if raw["expect"] not in ("block", "allow") or raw["kind"] not in ("html", "text"):
            raise ValueError(f"bad case {raw.get('id')}")
        cases.append(
            LeakCase(
                id=raw["id"],
                category=raw["category"],
                kind=raw["kind"],
                content=content,
                expect=raw["expect"],
                why=raw.get("why", ""),
            )
        )
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    literals = ["".join(x) if isinstance(x, list) else x for x in data.get("literals", [])]
    return list(data["terms"]), literals, cases


def run_case(case: LeakCase, terms: list[str], guardrails: Guardrails, literals: list[str]) -> bool:
    """True when the scanner blocks the case."""
    suffix = ".html" if case.kind == "html" else ".txt"
    return bool(scan_document(case.id, case.content, suffix, terms, guardrails, literals))


def run_leak_evals(
    cases_path: Path, guardrails_path: Path = Path("config/guardrails.yaml")
) -> EvalResult:
    terms, literals, cases = load_cases(cases_path)
    guardrails = load_guardrails(guardrails_path)
    result = EvalResult()
    for case in cases:
        blocked = run_case(case, terms, guardrails, literals)
        expected = case.expect == "block"
        result.total += 1
        result.by_category[case.category][1] += 1
        if blocked == expected:
            result.by_category[case.category][0] += 1
            if blocked:
                result.tp += 1
            else:
                result.tn += 1
        else:
            if blocked:
                result.fp += 1
            else:
                result.fn += 1
            outcome = "blocked" if blocked else "allowed"
            result.failures.append(
                f"{case.id} ({case.category}): {outcome}, expected {case.expect}"
            )
    return result
