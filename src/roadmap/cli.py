"""Command line entry point: ``roadmap build`` (design "Flow and orchestration")."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from roadmap.audit import audit_live, audit_repo, commit_author_emails
from roadmap.confidentiality import find_forbidden, load_terms, parse_terms
from roadmap.config import SiteConfig, load_config
from roadmap.evals import run_leak_evals
from roadmap.extract import fetch_raw, load_fixture, load_sa_from_env
from roadmap.leakscan import load_guardrails, scan_document, scan_site_dir
from roadmap.models import Issue, ParsedSheets, PublishedData, RawSheets
from roadmap.parse import parse_sheets
from roadmap.render import render_site
from roadmap.transform import build_published
from roadmap.validate import (
    check_future_dates,
    check_modules_mapped,
    check_publico,
    check_reconciliation,
    check_vanished_courses,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="roadmap")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="validate the sheet data and render the site")
    b.add_argument("--source", choices=["sheets", "fixture"], required=True)
    b.add_argument("--fixture", type=Path)
    b.add_argument("--config", type=Path, default=Path("config/site.yaml"))
    b.add_argument("--content", type=Path, default=Path("content"))
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--snapshot", type=Path)
    b.add_argument("--today", type=datetime.date.fromisoformat)
    b.add_argument("--forbidden-terms-file", type=Path)
    b.add_argument("--guardrails", type=Path, default=Path("config/guardrails.yaml"))

    live = sub.add_parser("audit-live", help="crawl the published site and scan it for leaks")
    live.add_argument("--url", help="defaults to base_url from the config")
    live.add_argument("--config", type=Path, default=Path("config/site.yaml"))
    live.add_argument("--guardrails", type=Path, default=Path("config/guardrails.yaml"))
    live.add_argument("--forbidden-terms-file", type=Path)

    repo = sub.add_parser("audit-repo", help="scan tracked files and git history for leaks")
    repo.add_argument("--path", type=Path, default=Path("."))
    repo.add_argument("--guardrails", type=Path, default=Path("config/guardrails.yaml"))
    repo.add_argument("--forbidden-terms-file", type=Path)
    repo.add_argument(
        "--strict-authors",
        action="store_true",
        help="fail when a commit author email is not a GitHub noreply address",
    )

    ev = sub.add_parser("eval-leaks", help="run the labelled leak-detection eval suite")
    ev.add_argument("--cases", type=Path, default=Path("evals/leak_cases.yaml"))
    return parser


def _terms(file: Path | None, required: bool) -> list[str] | None:
    """Terms from a file, else from FORBIDDEN_TERMS; None (after an error) if required and empty."""
    terms = parse_terms(file.read_text(encoding="utf-8")) if file else load_terms()
    if required and not terms:
        _err("FORBIDDEN_TERMS not set")
        return None
    return terms


def _runtime_literals() -> list[str]:
    """Values that must never be published: the sheet id and service-account identifiers."""
    literals = [os.environ.get("SHEET_ID", "")]
    raw = os.environ.get("GOOGLE_SA_JSON")
    if raw:
        try:
            info = json.loads(raw)
            literals += [
                str(info.get(k, "")) for k in ("client_email", "private_key_id", "client_id")
            ]
        except json.JSONDecodeError:
            pass
    return [lit for lit in literals if len(lit) >= 8]


def _report(issues: list[Issue]) -> int:
    for issue in issues:
        _err(issue.format())
    return 1 if issues else 0


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _load_previous(path: Path | None) -> PublishedData | None:
    if path is None or not path.exists():
        return None
    try:
        return PublishedData.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        _err("warning: previous snapshot could not be parsed; ignoring it")
        return None


def _walk(value: Any, loc: str, out: list[tuple[str, str]]) -> None:
    if isinstance(value, str):
        out.append((loc, value))
    elif isinstance(value, dict):
        for k, v in value.items():
            _walk(v, f"{loc}.{k}" if loc else str(k), out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk(v, f"{loc}[{i}]", out)


def _collect_texts(
    data: PublishedData, config: SiteConfig, content_dir: Path
) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    _walk(data.model_dump(mode="json"), "", texts)
    for md in sorted(content_dir.rglob("*.md")):
        rel = md.relative_to(content_dir).as_posix()
        texts.append((rel, md.read_text(encoding="utf-8")))
    texts.append(("config.headline", config.headline))
    texts.append(("config.summary", config.summary))
    return texts


def _write_summary(
    raw: RawSheets, parsed: ParsedSheets, data: PublishedData | None, issues: list[Issue]
) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    rows = [
        ("Publico rows read", len(raw.publico)),
        ("Cronograma rows parsed", len(parsed.cronograma)),
        ("Modules rows parsed", len(parsed.modules)),
    ]
    if data is not None:
        rows += [
            ("Public competencies", len(data.competencies)),
            ("Public courses", len(data.courses)),
            ("Public projects", len(data.projects)),
        ]
    by_rule = Counter(i.rule for i in issues)
    rows += [(f"Issues {r}", n) for r, n in sorted(by_rule.items())]
    rows.append(("Issues total", len(issues)))
    lines = ["| Metric | Count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows]
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def _build(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    today = args.today or datetime.datetime.now(datetime.UTC).date()
    content_dir: Path = args.content

    if args.source == "fixture":
        if args.fixture is None:
            _err("--fixture is required with --source fixture")
            return 2
        raw = load_fixture(args.fixture)
        terms = (
            parse_terms(args.forbidden_terms_file.read_text(encoding="utf-8"))
            if args.forbidden_terms_file
            else []
        )
    else:
        try:
            raw = fetch_raw(os.environ["SHEET_ID"], load_sa_from_env())
        except Exception as exc:
            _err(f"infrastructure error: {type(exc).__name__}")
            return 2
        terms = (
            parse_terms(args.forbidden_terms_file.read_text(encoding="utf-8"))
            if args.forbidden_terms_file
            else load_terms()
        )
        if not terms:
            _err("FORBIDDEN_TERMS not set")
            return 2
    guardrails = load_guardrails(args.guardrails)
    literals = _runtime_literals()

    parsed, issues = parse_sheets(raw, config.start_year)
    previous = _load_previous(args.snapshot)
    case_ids = {p.stem for p in (content_dir / "cases").glob("*.md")}
    issues = list(issues)
    issues += check_future_dates(parsed.cronograma, today)
    issues += check_publico(parsed.publico, case_ids)
    issues += check_modules_mapped(parsed.publico, parsed.modules)
    issues += check_reconciliation(parsed.cronograma, parsed.totals)
    issues += check_vanished_courses(parsed.publico, parsed.cronograma, previous)

    if issues:
        for issue in issues:
            _err(issue.format())
        _write_summary(raw, parsed, None, issues)
        return 1

    data = build_published(parsed, config, case_ids, today, previous, config.chart_min_weeks)

    q8 = find_forbidden(_collect_texts(data, config, content_dir), terms)
    if q8:
        for issue in q8:
            _err(issue.format())
        _write_summary(raw, parsed, data, q8)
        return 1

    snapshot_text = (
        json.dumps(data.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2)
        + "\n"
    )
    # Defense in depth: scan what will actually be published (rendered HTML/CSS and the
    # snapshot), not just the data, before anything is written to the snapshot or deployed.
    render_site(data, config, content_dir, args.out)
    leaks = scan_site_dir(args.out, terms, guardrails, literals)
    leaks += scan_document(
        "data/published.json", snapshot_text, ".json", terms, guardrails, literals
    )
    if leaks:
        shutil.rmtree(args.out, ignore_errors=True)
        _write_summary(raw, parsed, data, leaks)
        return _report(leaks)

    if args.snapshot is not None:
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        with args.snapshot.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(snapshot_text)

    _write_summary(raw, parsed, data, [])
    return 0


def _audit_live(args: argparse.Namespace) -> int:
    terms = _terms(args.forbidden_terms_file, required=True)
    if terms is None:
        return 2
    url = args.url or load_config(args.config).base_url
    guardrails = load_guardrails(args.guardrails)
    try:
        issues, pages = audit_live(url, terms, guardrails, _runtime_literals())
    except Exception as exc:
        _err(f"infrastructure error: {type(exc).__name__}")
        return 2
    print(f"audited {len(pages)} url(s); {len(issues)} issue(s)")
    return _report(issues)


def _audit_repo(args: argparse.Namespace) -> int:
    terms = _terms(args.forbidden_terms_file, required=True)
    if terms is None:
        return 2
    issues, n_files = audit_repo(
        args.path, terms, load_guardrails(args.guardrails), _runtime_literals()
    )
    authors = commit_author_emails(args.path)
    print(f"scanned {n_files} tracked file(s) and the full history; {len(issues)} issue(s)")
    if authors:
        # Never print the addresses themselves: the job log is public.
        msg = f"{len(authors)} commit author email(s) are not GitHub noreply addresses"
        if args.strict_authors:
            issues.append(Issue(tab="Content", row=None, rule="Q8", message=msg))
        else:
            _err(f"warning: {msg}")
    return _report(issues)


def _eval_leaks(args: argparse.Namespace) -> int:
    result = run_leak_evals(args.cases)
    print(result.summary())
    for failure in result.failures:
        _err(f"FAIL {failure}")
    return 0 if not result.failures else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    commands = {
        "build": _build,
        "audit-live": _audit_live,
        "audit-repo": _audit_repo,
        "eval-leaks": _eval_leaks,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
