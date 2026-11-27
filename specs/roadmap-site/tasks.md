# roadmap-site — Tasks

> Fase 4, 2026-11-27. Cada tarefa deve ser executável **sem acesso à conversa**: leia junto o `spec.md` (requisitos R*, regras RNF-Q) e o `design.md` (ADR-*, "Data model", "Regras de cálculo").
> Raiz do código: `c:\Users\lucas\projetos\roadmap-site\` (o repo é público; nunca commitar dados reais da planilha, credenciais ou termos proibidos).
> Convenções gerais (valem para todas as tarefas): Python 3.12, `from __future__ import annotations`, tipagem completa, pydantic v2, testes em `pytest`, lint com `ruff check .` (config na T1). Textos do site em inglês; comentários e docstrings em inglês.

## Grafo de dependências

```
T1 ─┬─ T2 ─┬─ T4 ─┬─ T5 ──┐
    │      │      ├─ T6* ─┤
    │      │      └─ T7 ──┤
    ├─ T3 ─┘              ├─ T8* ─┬─ T10 ─┐
    │                     │       └───────┼─ T11 ─┐
    │                     └─ T9* ─────────┤       ├─ T13 ─ T14 ─ T16 (manual) ─ T17*
    └─ T12 (depois de T2) ────────────────┴───────┘
    T15 (depois de T1, paralela a tudo)
```
`*` = tier strong (main session).

---

- [x] **T1 Scaffold do projeto** — covers [R6, A5] — tier: light
  - files (criar): `pyproject.toml`, `.gitignore`, `README.md` (só título + 1 parágrafo + "Status: work in progress"), `src/roadmap/__init__.py` (vazio), `config/site.yaml`, `tests/__init__.py` (vazio), `tests/conftest.py` (vazio)
  - `pyproject.toml`: projeto `roadmap-site`, versão `0.1.0`, `requires-python = ">=3.12"`, build backend `hatchling`, pacote em `src/roadmap`. Dependências: `google-api-python-client>=2.150`, `google-auth>=2.35`, `pydantic>=2.9`, `jinja2>=3.1`, `markdown-it-py>=3.0`, `pyyaml>=6.0`. Extra `dev`: `pytest>=8`, `ruff>=0.7`. Script: `roadmap = "roadmap.cli:main"`. `[tool.ruff] line-length = 100`, `target-version = "py312"`, `[tool.ruff.lint] select = ["E","F","I","UP","B"]`. `[tool.pytest.ini_options] testpaths = ["tests"]`.
  - `.gitignore`: `dist/`, `.venv/`, `__pycache__/`, `*.egg-info/`, `.env`, `*.sa.json`, `secrets/`, `.pytest_cache/`, `.ruff_cache/`
  - `config/site.yaml` (exatamente estas chaves; valores com placeholders):
    ```yaml
    name: "Lucas Lavnicki"
    headline: "Senior Data Engineer → AI Data Engineer"
    summary: "TODO: 1–2 sentences in English."
    links:
      - { label: "LinkedIn", url: "https://www.linkedin.com/in/TODO" }
      - { label: "GitHub", url: "https://github.com/TODO" }
    start_year: 2026
    chart_min_weeks: 4
    base_url: "https://TODO.github.io/roadmap-site/"
    repo_url: "https://github.com/TODO/roadmap-site"
    ```
  - Rodar `git init` em `roadmap-site/` (o diretório `specs/` já existe e entra no repo).
  - do not touch: `specs/`
  - done when: `python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"` instala sem erro e `ruff check .` passa — test: `.venv/Scripts/python -c "import roadmap"`

- [x] **T2 Modelos pydantic + config** — covers [R1–R4, R8] — tier: standard — (depends on T1) — [parallel with T3]
  - files (criar): `src/roadmap/models.py`, `src/roadmap/config.py`, `tests/test_models.py`
  - `models.py` deve conter exatamente (todos `BaseModel` com `model_config = ConfigDict(frozen=True, extra="forbid")`):
    - `Status = Literal["Done", "Planned", "Missed"]`
    - `RawSheets`: `publico: list[list[str]]`, `cronograma_totals: list[list[str]]`, `cronograma_left: list[list[str]]`, `cronograma_right: list[list[str]]`, `modules: list[list[str]]` (valores crus de cada range do design, "Extração")
    - `Issue`: `tab: str`, `row: int | None`, `rule: Literal["Q1","Q2","Q3","Q4","Q5","Q6","Q7","Q8"]`, `message: str`; método `def format(self) -> str` → `"[Q3] Cronograma row 12: <message>"` (sem `row` → `"[Q3] Cronograma: <message>"`)
    - `CronogramaTotals`: `planned: float`, `done: float`, `missed: float`
    - `CronogramaRow`: `row: int`, `date: datetime.date`, `course: str`, `hours: float`, `status: Status`
    - `ModuleRow`: `row: int`, `number: int`, `status: Literal["Done", "Planned"]`
    - `PublicoRow`: `row: int`, `tipo: Literal["competencia","curso","projeto","modulo"]`, `id: str`, `publicar: bool`, `ordem: int`, `nome_en: str`, `descricao_en: str | None`, `competencias: list[str]`, `provedor: str | None`, `cronograma_key: str | None`, `url: str | None`, `credencial_url: str | None`, `stack: list[str]`, `pai: str | None`, `status_manual: Literal["Done"] | None`, `horas_manual: float | None`
    - `ParsedSheets`: `totals: CronogramaTotals`, `cronograma: list[CronogramaRow]`, `modules: list[ModuleRow]`, `publico: list[PublicoRow]`
    - Modelos publicados, com os campos exatamente como no JSON do design ("Modelo publicado"): `Link`, `Profile`, `Kpis`, `Module` (`id, name, status`), `Competency`, `Course`, `Project`, `WeeklyPoint`, `PublishedData` (`schema_version: Literal[1] = 1`, `data_updated_at: datetime.date`, `profile`, `kpis`, `competencies`, `courses`, `projects`, `weekly`). Status de competência: `Literal["Not started","In progress","Done","Planned"]`; de curso: `Literal["Planned","In progress","Done"]`.
  - `config.py`: `class SiteConfig(BaseModel)` com as chaves de `config/site.yaml` (`links: list[Link]`) e `def load_config(path: Path) -> SiteConfig` (yaml.safe_load).
  - follow: design "Data model"; ADR-07 (`data_updated_at`)
  - do not touch: outros módulos
  - done when: os testes cobrem `Issue.format` (com e sem row), `extra="forbid"` rejeitando campo desconhecido e `load_config("config/site.yaml")` — test: `pytest tests/test_models.py -q`

- [x] **T3 Fixtures sintéticas** — covers [R1–R4, R8, RNF-Q] — tier: light — (depends on T1) — [parallel with T2]
  - files (criar): `tests/fixtures/valid.json`, `tests/fixtures/content/cases/private-proj.md`, `tests/fixtures/content/about.md`, `tests/fixtures/EXPECTED.md`
  - `valid.json` = objeto com as 5 chaves de `RawSheets`; cada valor é uma lista de linhas (lista de strings), exatamente:
    - `cronograma_totals`: `[["Horas planejadas","22,0"],["Horas concluídas","15,0"],["Horas não feitas","1,0"]]`
    - `cronograma_left` (linha 1 = cabeçalho): `["Data","Dia","Curso"]`, depois, em ordem: `28/12,Seg,Curso Alpha` · `29/12,Ter,Interno X` · `30/12,Qua,Curso Alpha` · `05/01,Seg,Curso Beta` · `06/01,Ter,Interno X` · `12/01,Seg,Curso Alpha` · `19/01,Seg,Curso Beta` · `26/01,Seg,Curso Alpha` · `27/01,Ter,Curso Beta` · `28/01,Qua,Curso Gamma`
    - `cronograma_right`: `["Horas","Status"]`, depois, na mesma ordem: `2,0 Feito` · `1,0 Não feito` · `3,0 Feito` · `4,0 Feito` · `2,0 Feito` · `1,5 Feito` · `2,5 Feito` · `3,0 A fazer` · `2,0 A fazer` · `1,0 A fazer` (cada linha é `["2,0","Feito"]` etc.)
    - `modules`: `[["Módulo","Tema","Horas","Status"],["1","Fundamentos","14","Feito"],["2","Avançado","14","A fazer"]]`
    - `publico`: cabeçalho `["tipo","id","publicar","ordem","nome_en","descricao_en","competencias","provedor","cronograma_key","url","credencial_url","stack","pai","status_manual","horas_manual"]`, depois as linhas (campos vazios = `""`):
      1. `competencia, data-platforms, sim, 1, Data Platforms, Building batch and streaming data platforms.`
      2. `competencia, llm-engineering, sim, 2, LLM Engineering, Building data pipelines for LLM applications.`
      3. `competencia, secret-comp, não, 3, Secret Competency, Hidden.`
      4. `curso, alpha, sim, 1, Alpha Course, , data-platforms, Provider A, Curso Alpha`
      5. `curso, beta, sim, 2, Beta Course, , data-platforms, Provider B, Curso Beta`
      6. `curso, delta, sim, 3, Delta Certification, , data-platforms, Provider D, , , https://example.com/cred/delta, , , Done, "10,0"`
      7. `curso, gamma, não, 4, Gamma Course, , data-platforms, Provider G, Curso Gamma`
      8. `projeto, public-proj, sim, 1, Public Project, A public demo pipeline., data-platforms, , , https://github.com/example/public-proj, , Python;Airflow`
      9. `projeto, private-proj, sim, 2, Private Project, A private agent project., llm-engineering, , , , , Python;LLM`
      10. `projeto, hidden-proj, sim, 3, Hidden Project, Must not appear., secret-comp, , , https://github.com/example/hidden, , Python`
      11. `modulo, alpha-m1, sim, 1, Module 1 – Foundations, , , , , , , , alpha`
      12. `modulo, alpha-m2, sim, 2, Module 2 – Advanced, , , , , , , , alpha`
  - `private-proj.md`: `# Private Project` + 3 seções curtas `## Problem`, `## Architecture`, `## Results` com texto genérico em inglês. `about.md`: 2 parágrafos genéricos sobre o pipeline.
  - `EXPECTED.md`: copie literalmente o bloco "Valores esperados" abaixo (é o oráculo para a T8 e a T13).
  - **Valores esperados** (com `start_year=2026`, `today=2027-02-01`, `chart_min_weeks=4`):
    - Datas: linhas 28/12–30/12 → 2026; 05/01 em diante → 2027.
    - Reconciliação: Σ Feito = 15,0; Σ Não feito = 1,0; Σ todas = 22,0 → bate com os totais.
    - alpha: done 6,5, planned 9,5, In progress, módulos `alpha-m1` Done e `alpha-m2` Planned. beta: done 6,5, planned 8,5, In progress. delta: done 10,0, planned 10,0, Done (manual), credential_url preenchido. gamma, Interno X e linha Missed: ausentes.
    - data-platforms: done 23,0, planned 28,0, pct 82,1, In progress, courses `[alpha, beta, delta]`, projects `[public-proj]`. llm-engineering: planned 0 → status Planned, pct null, courses `[]`, projects `[private-proj]`. secret-comp e hidden-proj: ausentes.
    - KPIs: hours_done 23,0; hours_planned_total 28,0; pct_plan 82,1; courses_done 1; courses_total 3; study_start 2026-12-28.
    - weekly (só horas do Cronograma, sem manual): `2026-12-28 → 5,0`; `2027-01-04 → 9,0`; `2027-01-11 → 10,5`; `2027-01-18 → 13,0` (4 semanas ≥ 4, então o gráfico aparece).
  - do not touch: `src/`
  - done when: `python -c "import json;d=json.load(open('tests/fixtures/valid.json',encoding='utf-8'));assert set(d)=={'publico','cronograma_totals','cronograma_left','cronograma_right','modules'};assert len(d['cronograma_left'])==len(d['cronograma_right'])==11;assert len(d['publico'])==13"` passa

- [x] **T4 Parsing (pt-BR, datas, status, aba Publico)** — covers [RNF-Q 1–4, A3] — tier: standard — (depends on T2, T3)
  - files (criar): `src/roadmap/parse.py`, `tests/test_parse.py`
  - Funções (assinaturas exatas):
    - `parse_ptbr_number(s: str) -> float` — aceita `"2,0"`, `"2"`, `" 1,5 "`, `"14"`; rejeita `""`, `"1.5"`, `"abc"`, `"1,2,3"` com `ValueError`.
    - `parse_status(s: str) -> Status` — `"Feito"→"Done"`, `"A fazer"→"Planned"`, `"Não feito"→"Missed"` (comparar com `strip()` e case-insensitive); outro valor → `ValueError`.
    - `infer_dates(ddmm: list[str], start_year: int) -> list[datetime.date]` — ano começa em `start_year` e avança +1 sempre que o mês for **menor** que o mês da linha anterior; data inválida (ex. `"31/02"`, `"1/1"`, `"aa/bb"`) → `ValueError` com o índice. Formato estrito `^\d{2}/\d{2}$`.
    - `parse_sheets(raw: RawSheets, start_year: int) -> tuple[ParsedSheets, list[Issue]]` — nunca lança exceção por dado ruim: cada problema vira um `Issue` e a linha é descartada.
      - Q1 (esquema): `cronograma_left[0] == ["Data","Dia","Curso"]`, `cronograma_right[0] == ["Horas","Status"]`, `modules[0][:4] == ["Módulo","Tema","Horas","Status"]`, `publico[0]` igual ao cabeçalho de 15 colunas da T3, e os 3 rótulos de `cronograma_totals`. Se o cabeçalho de uma aba falhar, emita 1 `Issue` Q1 (tab = `"Cronograma"`, `"Spark & Databricks"` ou `"Publico"`) e não processe essa aba.
      - Alinhamento: completar `cronograma_left`/`cronograma_right` com `[]` até o mesmo tamanho; completar cada linha com `""` até a largura do cabeçalho. Linhas totalmente vazias são ignoradas. Número da linha na planilha: `row = índice + 4` para o Cronograma (o índice 0 é o cabeçalho, na linha 4), `row = índice + 1` para Publico e módulos.
      - Q2: data não parseável → Issue Q2 com row. Q3: horas não parseáveis ou fora de `0 ≤ h ≤ 12` → Q3. Q4: status inválido → Q4.
      - Publico: `publicar` = `strip().lower() == "sim"`; `ordem` int (inválido → Q5); `competencias`/`stack` = split por `;` com strip, sem vazios; strings vazias → `None`; `horas_manual` com `parse_ptbr_number` (inválido → Q3); `status_manual` só `""` ou `"Done"` (outro → Q5); `tipo` fora do enum → Q5.
      - Mensagens de Issue podem citar só valores de Data, Curso, Horas, Status e das colunas da Publico (ADR-04).
  - follow: ADR-04, ADR-08, design "Quality" (inferência de ano)
  - do not touch: `models.py` (se faltar algo, pare e reporte)
  - done when: os testes cobrem cada caso de `parse_ptbr_number`/`parse_status`/`infer_dates` listado acima, a virada 12→01, e `parse_sheets` sobre `valid.json` → 0 issues, 10 linhas de Cronograma, 2 módulos, 12 linhas Publico, datas de 2026/2027 como em EXPECTED.md; e cabeçalho errado → 1 Issue Q1 — test: `pytest tests/test_parse.py -q`

- [x] **T5 Validação de datas futuras e unicidade/integridade (Q2, Q5, Q6)** — covers [R7, RNF-Q 2, 5, 6] — tier: standard — (depends on T4) — [parallel with T6, T7]
  - files (criar): `src/roadmap/validate.py`, `tests/test_validate.py`
  - Funções:
    - `check_future_dates(rows: list[CronogramaRow], today: date) -> list[Issue]` — Q2 se `row.date > today + 1 dia` e `status != "Planned"`.
    - `check_publico(rows: list[PublicoRow], case_ids: set[str]) -> list[Issue]` — tab `"Publico"`:
      - Q6: `(tipo, id)` duplicado; `id` fora de `^[a-z0-9-]+$`; `cronograma_key` repetido entre cursos.
      - Q5, só para linhas com `publicar=True`: `nome_en` vazio; competencia/projeto sem `descricao_en`; curso/projeto sem competência ou com competência inexistente na aba; projeto sem `url` e sem `id` em `case_ids`; `url`/`credencial_url` que não comece com `https://`; `status_manual="Done"` sem `horas_manual`; modulo com `pai` inexistente ou `id` fora de `^{pai}-m\d+$`.
    - `check_modules_mapped(publico, modules) -> list[Issue]` — Q5 se um modulo público aponta para um número que não existe na aba de módulos.
  - follow: spec RNF-Q 5–6; ADR-03; ADR-05
  - do not touch: `parse.py`, `models.py`
  - done when: um teste por regra (fixture válida + 1 mutação por caso), e `valid.json` com `case_ids={"private-proj"}` → 0 issues — test: `pytest tests/test_validate.py -q`

- [x] **T6 Reconciliação (Q7) + sonda K1 nos dados reais** — covers [RNF-Q 7, K1] — tier: strong — (depends on T4) — [parallel with T5, T7]
  - files: `src/roadmap/validate.py` (adicionar `check_reconciliation(rows: list[CronogramaRow], totals: CronogramaTotals, tol: float = 0.1) -> list[Issue]`), `tests/test_reconciliation.py`
  - Regra inicial: done = Σ Done, missed = Σ Missed, planned = Σ todas. Rodar uma sonda local (script temporário fora do repo, lendo a planilha real com credencial local) para confirmar a fórmula de "Horas planejadas" (133,5 em 2026-11-27). Se não bater, ajustar a regra e atualizar `design.md` (Quality) e EXPECTED.md.
  - do not touch: dados reais no repo
  - done when: teste com a fixture (bate) e uma mutação (diferença de 0,2h → Issue Q7); a sonda real bate — test: `pytest tests/test_reconciliation.py -q`

- [x] **T7 Detecção de curso que sumiu (K3)** — covers [R7, K3] — tier: standard — (depends on T4) — [parallel with T5, T6]
  - files: `src/roadmap/validate.py` (adicionar `check_vanished_courses(publico: list[PublicoRow], rows: list[CronogramaRow], previous: PublishedData | None) -> list[Issue]`), `tests/test_vanished.py`
  - Regra: para cada curso público com `cronograma_key` e sem `status_manual`, se `previous` tem esse `id` com `hours_done > 0` e nenhuma linha do Cronograma tem `course == cronograma_key` → Issue Q5 (tab `"Publico"`, row do curso, mensagem `"course '<id>' had published hours but its cronograma_key matches no Cronograma row"`). Com `previous=None` → nunca emite.
  - do not touch: `check_reconciliation`, `check_publico`
  - done when: 3 testes (previous None; curso presente; curso sumido) — test: `pytest tests/test_vanished.py -q`

- [x] **T8 Transformação + cálculos (allowlist, R1–R4)** — covers [R1, R2, R3, R4, R8] — tier: strong — (depends on T5, T6, T7)
  - files: `src/roadmap/transform.py`, `tests/test_transform.py`
  - `build_published(parsed: ParsedSheets, config: SiteConfig, case_ids: set[str], today: date, previous: PublishedData | None, min_weeks: int) -> PublishedData` seguindo design "Regras de cálculo" e ADR-07/08 (incluindo `data_updated_at`: compara com `previous` ignorando esse campo).
  - done when: o resultado sobre `valid.json` bate com todos os itens de EXPECTED.md; com `min_weeks=5`, `weekly == []`; dois builds iguais → `model_dump_json` idêntico — test: `pytest tests/test_transform.py -q`

- [x] **T9 Confidencialidade (Q8)** — covers [R8, RNF-Q 8] — tier: strong — (depends on T2) — [parallel with T4–T8]
  - files: `src/roadmap/confidentiality.py`, `tests/test_confidentiality.py`
  - `load_terms(env_var: str = "FORBIDDEN_TERMS") -> list[str]`; `find_forbidden(texts: list[tuple[str, str]], terms: list[str]) -> list[Issue]` (location, text) — case-insensitive, sem acentos (NFKD), palavra inteira; a mensagem cita só a location, **nunca** o termo.
  - done when: testes com termos fictícios (`acme-corp`, `Cliente Fictício`) cobrem maiúsculas, acento, palavra parcial (não pode disparar) e a mensagem sem o termo — test: `pytest tests/test_confidentiality.py -q`

- [x] **T10 Gráfico SVG semanal** — covers [R4, R9] — tier: standard — (depends on T8)
  - files (criar): `src/roadmap/chart.py`, `tests/test_chart.py`
  - `render_weekly_svg(points: list[WeeklyPoint], width: int = 640, height: int = 200) -> str` — retorna `""` se `points` vazio. Senão: `<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="chart-title">` com `<title id="chart-title">Cumulative study hours per week</title>`, uma `<polyline>` (classe `line`) dos pontos, um `<circle r="3">` por ponto, rótulos do eixo x com `week_start` no formato `"Dec 28"` (só o primeiro e o último) e rótulo y do valor final (`"13.0 h"`). Margens de 32px. Sem estilos inline de cor: usar `stroke="currentColor"` (o tema vem do CSS). Saída determinística (coordenadas com 1 casa decimal).
  - follow: ADR-02
  - do not touch: `transform.py`
  - done when: testes: vazio → `""`; os 4 pontos de EXPECTED.md → contém `<title`, 4 `<circle`, `"Dec 28"`, `"13.0 h"`, e duas chamadas dão a mesma string — test: `pytest tests/test_chart.py -q`

- [x] **T11 Templates, CSS e render** — covers [R1, R2, R3, R4, R5, R9] — tier: standard — (depends on T8, T10)
  - files (criar): `src/roadmap/render.py`, `templates/base.html`, `templates/index.html`, `templates/case.html`, `templates/partials/{hero,competency_card,course_list,project_card,how_it_works}.html`, `static/style.css`, `tests/test_render.py`
  - `render_site(data: PublishedData, config: SiteConfig, content_dir: Path, out_dir: Path) -> list[Path]` — limpa e recria `out_dir`; escreve `index.html`, `cases/<id>.html` para cada projeto com `case_path`, `style.css` (cópia) e `.nojekyll` (vazio). Jinja2 `Environment(loader=FileSystemLoader("templates"), autoescape=True, undefined=StrictUndefined, keep_trailing_newline=True)`. Markdown via `MarkdownIt("commonmark", {"html": False})`.
  - Conteúdo de `index.html` (ordem, ADR-06): hero (`<h1>` name, headline, summary, links, KPIs: "Hours completed", "% of plan", "Courses completed X/Y", "Studying since <Mon YYYY>") → gráfico (só se `weekly` não for vazio) → `<section id="competencies">` com um card por competência (status em texto + barra `<progress value max="100">` com `aria-label`; se `pct` é null, mostra "Planned" sem barra; cursos com módulos em `<details>`; projetos) → `<section id="courses">` (nome, provider, status, `hours_done/hours_planned h`, link "View credential" se houver) → `<section id="projects">` (title, description, stack como `<ul>`, link "Repository" ou "Read the case study") → `<section id="how-this-site-works">` (`content/about.md` renderizado + diagrama em texto/lista "Google Sheets → validation → JSON → static site", link `repo_url`, "Data last updated: YYYY-MM-DD").
  - HTML: `<html lang="en">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, `<meta name="description">`, um único `<h1>`, sem `<script>`, sem fontes externas.
  - CSS: mobile-first, fonte `system-ui`, largura máx. 960px, `padding-inline: 16px`, nada com largura fixa > 360px, contraste AA, `@media (prefers-color-scheme: dark)` com variáveis em `:root`.
  - follow: ADR-02, ADR-05, ADR-06, R9
  - do not touch: `transform.py`, `chart.py`
  - done when: testes renderizam a partir do `PublishedData` da fixture (via `build_published`) e checam: `index.html` sem `<script`; contém "Data Platforms" e não contém "Secret Competency", "Hidden Project" nem "Gamma Course"; "View credential" aparece 1 vez; existe `cases/private-proj.html`; "Interno X" não aparece em nenhum arquivo — test: `pytest tests/test_render.py -q`

- [x] **T12 Extração do Google Sheets** — covers [R6, R8, ADR-04] — tier: standard — (depends on T2) — [parallel with T4–T11]
  - files (criar): `src/roadmap/extract.py`, `tests/test_extract.py`
  - Constantes: `RANGES = {"publico": "Publico!A1:O", "cronograma_totals": "Cronograma!A1:B3", "cronograma_left": "Cronograma!A4:C", "cronograma_right": "Cronograma!E4:F", "modules": "'Spark & Databricks'!A1:D"}`; `SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]`.
  - `fetch_raw(sheet_id: str, sa_info: dict) -> RawSheets` — `service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)`; `build("sheets", "v4", credentials=..., cache_discovery=False)`; uma chamada `values().batchGet(spreadsheetId=..., ranges=list(RANGES.values()), valueRenderOption="FORMATTED_VALUE")`; mapeia `valueRanges[i].get("values", [])` na ordem de `RANGES`. `load_sa_from_env(var="GOOGLE_SA_JSON") -> dict` (json.loads; ausente → `RuntimeError("GOOGLE_SA_JSON not set")`). **Nunca** logar `sa_info`, `sheet_id` nem valores.
  - `load_fixture(path: Path) -> RawSheets`.
  - Testes sem rede: mockar `googleapiclient.discovery.build` com `unittest.mock` e checar que `batchGet` recebe exatamente os 5 ranges, que nenhum range contém `!D` de Cronograma nem a coluna E de módulos, e que `load_fixture(valid.json)` funciona.
  - do not touch: outros módulos
  - done when: — test: `pytest tests/test_extract.py -q`

- [x] **T13 CLI + snapshot + golden + determinismo** — covers [R6, R7, ADR-07] — tier: standard — (depends on T8, T9, T11, T12)
  - files (criar): `src/roadmap/cli.py`, `tests/test_cli.py`, `tests/fixtures/expected_published.json` (gerado pelo próprio build sobre a fixture com `--today 2027-02-01` e **conferido contra EXPECTED.md** antes de salvar)
  - `main(argv: list[str] | None = None) -> int` com argparse: `build --source {sheets,fixture} [--fixture PATH] [--config config/site.yaml] [--content content] --out dist [--snapshot data/published.json] [--today YYYY-MM-DD] [--forbidden-terms-file PATH]`.
  - Fluxo: carregar config → raw (sheets: `fetch_raw(os.environ["SHEET_ID"], load_sa_from_env())`; fixture: `load_fixture`) → `parse_sheets` → `previous` = snapshot se existir → issues de T5/T6/T7 → se houver issues: imprimir `issue.format()` em stderr, um por linha, e retornar 1 → `build_published` → textos para Q8 (todos os campos string do JSON + `.md` de content + summary/headline) → termos (`--forbidden-terms-file`, senão `load_terms()`; em `--source sheets`, lista vazia → stderr `"FORBIDDEN_TERMS not set"` e retorna 2) → se Q8 falhar, retorna 1 → gravar snapshot (`json.dumps(data.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2) + "\n"`, UTF-8, LF) → `render_site` → escrever resumo em `$GITHUB_STEP_SUMMARY` se existir (só contagens) → retorna 0. Erros de API/credencial → retorna 2.
  - follow: ADR-04, ADR-07, design "Flow"
  - done when: testes: fixture → exit 0 e snapshot == `expected_published.json`; rodar duas vezes → `dist/` idêntico byte a byte (hash de todos os arquivos); mutação com hora "13,0" → exit 1 e stderr contém `[Q3]`; termo `"Alpha"` no arquivo de termos → exit 1 e stderr não contém "Alpha" — test: `pytest -q` (suíte completa) e `ruff check .`

- [x] **T14 Workflows do GitHub Actions** — covers [R6, R7, ADR-01, ADR-04] — tier: standard — (depends on T13)
  - files (criar): `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
  - `ci.yml`: `on: [push, pull_request]`; ubuntu-latest; `actions/checkout@v4`, `actions/setup-python@v5` (3.12, cache pip); `pip install -e ".[dev]"`; `ruff check .`; `pytest -q`; `roadmap build --source fixture --fixture tests/fixtures/valid.json --content tests/fixtures/content --out dist --today 2027-02-01`. Sem secrets.
  - `publish.yml`: `on: schedule: [{cron: "0 9 * * *"}]` + `workflow_dispatch`; `permissions: {contents: write, pages: write, id-token: write}`; `concurrency: {group: publish, cancel-in-progress: false}`. Job `build`: checkout, setup-python, `pip install .`, step `roadmap build --source sheets --out dist --snapshot data/published.json` com `env: {GOOGLE_SA_JSON: ${{ secrets.GOOGLE_SA_JSON }}, SHEET_ID: ${{ secrets.SHEET_ID }}, FORBIDDEN_TERMS: ${{ secrets.FORBIDDEN_TERMS }}}`; step de commit: `git diff --quiet data/published.json || (git config user.name "github-actions[bot]" && git config user.email "41898282+github-actions[bot]@users.noreply.github.com" && git add data/published.json && git commit -m "data: snapshot $(date -u +%F)" && git push)`; `actions/upload-pages-artifact@v3` com `path: dist`. Job `deploy` (needs build, `environment: github-pages`): `actions/deploy-pages@v4`.
  - do not touch: código Python
  - done when: `python -c "import yaml;[yaml.safe_load(open(f)) for f in ['.github/workflows/ci.yml','.github/workflows/publish.yml']]"` passa e nenhum `echo` imprime secrets — test: revisão do diff na main session

- [x] **T15 Docs e conteúdo** — covers [R5, K2, K6] — tier: light — (depends on T1) — [parallel with T2–T14]
  - files: `README.md` (o que é, diagrama Mermaid copiado do design, como rodar local com a fixture, setup dos secrets, nota do K2 sobre cron desativado após 60 dias), `content/about.md` (rascunho em inglês, 2 parágrafos, marcado `<!-- TODO Lucas: review -->`), `docs/publico-template.csv` (só o cabeçalho de 15 colunas da T3 + 1 linha de exemplo por `tipo`, dados fictícios), `content/cases/job-search-agent.md` (esqueleto com `## Problem`, `## Architecture`, `## Stack`, `## Results` e `TODO`).
  - do not touch: `src/`, `tests/`
  - done when: os arquivos existem e o CSV tem 15 colunas em todas as linhas — test: `python -c "import csv;r=list(csv.reader(open('docs/publico-template.csv',encoding='utf-8')));assert all(len(x)==15 for x in r)"`

- [x] **T16 Setup manual (Lucas)** — covers [R6, R8, K6, K7] — tier: manual (Lucas) — (depends on T14, T15)
  - Criar o projeto no Google Cloud, ativar a Sheets API, criar a service account sem papéis e gerar a chave JSON. Compartilhar a planilha com o e-mail da SA como **Leitor**.
  - Criar o repo público no GitHub e definir os secrets `GOOGLE_SA_JSON`, `SHEET_ID`, `FORBIDDEN_TERMS`. Em Settings → Pages, escolher Source = GitHub Actions.
  - Criar a aba `Publico` a partir de `docs/publico-template.csv`, com as linhas reais (FDE com `status_manual=Done`, Spark & Databricks com os módulos) e textos em inglês.
  - Preencher os TODO de `config/site.yaml`, `content/about.md` e `content/cases/job-search-agent.md`.
  - done when: `Run workflow` manual do `publish.yml` termina verde

- [x] **T17 Primeira publicação real + aceite** — covers [R1–R9, métricas] — tier: strong — (depends on T16)
  - Rodar o workflow, abrir o site no celular (360px) e no desktop, rodar Lighthouse mobile (≥ 90 em Performance e Accessibility) e conferir no site publicado que não há "Observação", "Entrevistas", DevSpeak nem bootcamps. Rodar o workflow de novo sem mudar a planilha → sem commit novo (idempotência). Quebrar uma hora de propósito numa cópia de teste → e-mail de falha. Revisar o inglês com o Lucas.
  - done when: checklist acima ok; link pronto para CV/LinkedIn

## Mudanças pós-lançamento (2026-11-27)

Pedidas pelo Lucas depois da T17. Implementadas na main session (tier: standard/strong) e registradas aqui para manter a rastreabilidade spec → design → task → teste.

- [x] **T18 Case sem plataforma de vagas e com filtro genérico** — covers [R2, R8] — tier: light
  - files: `content/cases/job-search-agent.md` (renomeado de outro slug), aba `Publico` (id do projeto), `tests/test_content.py`
  - done when: nenhum case cita plataformas de vagas no texto ou no slug — test: `pytest tests/test_content.py`
- [x] **T19 Competência conta projeto e curso começado como progresso** — covers [R1] — tier: standard — follow: ADR-10
  - files: `src/roadmap/transform.py` (`_competency_status`), `templates/partials/competency_card.html`, fixtures `EXPECTED.md`/`expected_published.json`
  - done when: tabela de regras coberta — test: `pytest tests/test_transform.py -k competency`
- [x] **T20 Cursos manuais Done/In progress com horas `feito/total`** — covers [R3, R4] — tier: strong — follow: ADR-10
  - files: `src/roadmap/models.py`, `parse.py`, `validate.py`, `transform.py`, `templates/partials/course_list.html`; aba `Publico` (linhas `aide` e `forward-deployed-engineer`)
  - done when: formatos aceitos/rejeitados e regras de validação testados — test: `pytest tests/test_parse.py -k horas_manual tests/test_validate.py -k manual`
- [x] **T21 Data de início configurável** — covers [R4] — tier: light — follow: ADR-10
  - files: `src/roadmap/config.py` (`studying_since`), `config/site.yaml` (`2026-09-01`), `transform.py`
  - done when: override e fallback testados — test: `pytest tests/test_transform.py -k studying_since`
- [x] **T22 SDD citado nos projetos e módulos fora do site** — covers [R1, R2, R5] — tier: light
  - files: `content/about.md`, case, descrições na aba `Publico`, `config/site.yaml` (`platform`); módulos do Spark & Databricks com `publicar=não`
  - done when: publicação verde e auditoria do site no ar sem issues — test: `roadmap audit-live`
- [x] **T23 Linha de idioma no topo** — covers [R9, R8] — tier: light — follow: ADR-11
  - files: `src/roadmap/config.py` (`languages: list[str] = []`), `config/site.yaml`, `templates/partials/hero.html`, `static/style.css`, `tests/test_render.py`
  - do not touch: aba `Publico`, `config/guardrails.yaml` (o nome da escola continua bloqueado)
  - done when: a linha aparece no hero quando configurada e some quando vazia — test: `pytest tests/test_render.py -k languages`
