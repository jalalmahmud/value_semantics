# Adjudication Rubric — VSL Evaluation

These criteria define how a generated query is judged against a case's intent and expected behavior.
They were applied during a **retrospective adjudication** of the evaluation's labels; they were not
fixed prior to the original evaluation. Each criterion is applied identically to all four conditions
(data-dictionary, matched prose, prompt-mediated, planner-enforced); the same criterion may yield
different verdicts for different conditions.

## Verdict scale

- **correct (fully resolved):** the query operationalizes the intent — all required components are
  satisfied under a defensible reading.
- **partial:** the query satisfies some but not all required components (e.g., right computation shape
  but an unsupported ordering; a related quantity rather than the required one).
- **incorrect (unresolved):** the query satisfies none of the required components, or cannot return the
  intended result.

## Criteria

### C1. Density / rate tasks
A query claiming a **density** or **rate** must use a stated, appropriate **denominator** (e.g., area
for spatial density; exposure or population for risk). Counts alone do not receive full credit for a
density/rate intent; they are at most partial. If no valid denominator exists in the data, the task is
unsupported (see C3).

### C2. Trends across stages / over time
A query claiming a trend **across career stages or over time** must order on a dimension with
**evidence that it represents the required progression** (a date/time field, documented ordinal
semantics, or source-generation documentation). A trend computed over an unverified or invalid ordering
(e.g., an identifier or a title string), or a single snapshot where a trend is required, is at most
partial.

### C3. Unsupported tasks
A task is unsupported when the data cannot, even in principle, satisfy the intent (no valid denominator;
no evidence of the required ordering; a required quantity absent). **For this evaluation, unsupported
tasks were retained** (not excluded from the 124): each condition is scored against the best attainable
operationalization, so the closest supportable query is `partial`, not `incorrect`, and all four
conditions are scored the same way.

Scope note: this criterion was applied during the **retrospective adjudication of the flagged cases**
(the cases the audit surfaced). It was *not* re-run as a systematic sweep that re-examined every
potentially-unsupported case across all 124; a complete independent re-judgment of the full set was not
performed (see the README Limitations).

### C4. Partial resolution
`partial` records which required components are satisfied and which are missing; it is not an automatic
outcome for uncertainty. A query that satisfies none of the required components is `incorrect`; one that
satisfies all is `correct`.
