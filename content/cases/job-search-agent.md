# Job Search Agent

*Private repository: this page summarizes the project.*

## Problem

Searching for jobs across several boards is repetitive, and most postings are not a fit. Some postings should never get an application at all, so the search needs hard rules, not just preferences. An LLM can help rank postings, but it cannot be trusted to make the final decision or to enforce those rules.

## Architecture

- **Collection:** open job APIs (Himalayas, Jobicy) and the Greenhouse, Lever and Ashby career pages of companies I approve. New sources plug in behind the same interface. Postings are deduplicated across sources and stored in SQLite with a full status history.
- **Triage pipeline:** every posting goes through the same steps: a deterministic, **fail-closed company filter** (any company can be added to a blocklist in configuration), language and remote filters, a **prompt-injection detector**, and an LLM score. Triage can only block or rank. It never approves.
- **LLM layer:** pluggable provider, either local (Ollama, nothing leaves the machine) or the Claude API. The model may only *add* restrictions. If it fails, the posting waits for review instead of passing.
- **Human in the loop:** only I approve a posting. Before any submission the company filter runs again on the live page, and the form is submitted only after my explicit confirmation. Dry-run is the default.
- **Interfaces:** a CLI and a local web app (FastAPI).

## How it was built

The project follows **spec-driven development (SDD)**: every feature starts as a spec (problem, requirements with acceptance criteria), then a design with ADRs, then a task list, and only then code. The project has 9 specs and 11 ADRs.

## Stack

Python, Pydantic, Playwright, FastAPI, SQLite, Claude API, Ollama, pytest.

## Results

- **Evals as tests:** 70+ labelled cases for scoring, eligibility and prompt injection, plus an offline eval for the company filter. They make it possible to compare models and providers before switching.
- **Around 490 automated tests.**
- **Cost control:** a per-search cap on how many postings go to the paid model, and usage reports by source.
