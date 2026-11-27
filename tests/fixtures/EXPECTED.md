# Expected values for tests/fixtures/valid.json

- **Valores esperados** (com `start_year=2026`, `today=2027-02-01`, `chart_min_weeks=4`):
    - Datas: linhas 28/12–30/12 → 2026; 05/01 em diante → 2027.
    - Reconciliação: Σ Feito = 15,0; Σ Não feito = 1,0; Σ todas = 22,0 → bate com os totais.
    - alpha: done 6,5, planned 9,5, In progress, módulos `alpha-m1` Done e `alpha-m2` Planned. beta: done 6,5, planned 8,5, In progress. delta: done 10,0, planned 10,0, Done (manual), credential_url preenchido. gamma, Interno X e linha Missed: ausentes.
    - data-platforms: done 23,0, planned 28,0, pct 82,1, In progress, courses `[alpha, beta, delta]`, projects `[public-proj]`. llm-engineering: planned 0 mas com projeto público → status In progress, pct null, courses `[]`, projects `[private-proj]`. secret-comp e hidden-proj: ausentes.
    - KPIs: hours_done 23,0; hours_planned_total 28,0; pct_plan 82,1; courses_done 1; courses_total 3; study_start 2026-12-28.
    - weekly (só horas do Cronograma, sem manual): `2026-12-28 → 5,0`; `2027-01-04 → 9,0`; `2027-01-11 → 10,5`; `2027-01-18 → 13,0` (4 semanas ≥ 4, então o gráfico aparece).
