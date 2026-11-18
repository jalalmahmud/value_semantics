# VSL Vision Paper — Supplemental Materials

Supporting materials **and code** for the paper's preliminary evaluation on a curated diagnostic set:
the VSL implementation, the generation runners, the rubric, the final per-case labels, the generated
SQL, the generation prompts, and a script that regenerates the reported numbers from the labels.

**Reproduces (124 evaluated cases):** fully-resolved — data-dictionary 17, matched prose 20, PM 35,
PE 51 (PM–PE gap 16); PE full+partial 92.7%. Run `recompute_vsl_eval.py`.

> **Public release note (HR withheld).** To protect proprietary HR data, this release withholds all HR
> **per-case** material — the HR case definitions (`hr_benchmark_v2.json`), the HR sections of the
> human-eval sheets, and HR rows of the corrections log — in addition to the HR registry, raw records, and
> de-anonymization maps. HR's **aggregate verdict labels are retained** in `vsl_final_labels.csv`, so the
> paper's Table 2 totals still reproduce exactly. **Finance** (BIRD) and **Public Safety** (NYC Open Data)
> are fully inspectable and rerunnable. The one-time label-build script is omitted; reproduction reads
> `vsl_final_labels.csv` via `recompute_vsl_eval.py`.

---

## 0. Scope — what you can reproduce

This package includes the **VSL implementation** (`value_semantics/`) and the **generation runners**, so
the core experiment can be *rerun*, not just inspected. It is a *preliminary* supplemental artifact for a
**vision** paper; we do not claim it satisfies VLDB's stronger full-artifact requirement (stated for
EA&B papers).

**Supported by this package:**
- **Inspection** of every **finance and public-safety** case: the natural-language intent, the generated
  SQL for all four conditions, and the per-case verdict and rationale. (HR per-case material is withheld;
  only HR's aggregate verdict labels are retained — see the release note above.)
- **Recomputation of Table 2** from the authoritative final labels: `recompute_vsl_eval.py`
  (standard library only; no model or database).
- **Rerunning SQL generation** for all four conditions on **finance** and **public safety**: the runners
  load the shipped JSON registries and call the model API (GPT-4o) — **no database needed**. Requires
  `pip install -r requirements.txt`, an `OPENAI_API_KEY`, and the `--run` flag (the D1/D2 baseline runner
  defaults to a dry run). The D1/D2 baseline reads the shipped author-reviewed data dictionaries. See §3.
- **Rebuilding the public-safety VST registry from raw data** — `demos/build_ps_registry_v2engine.py`
  runs the `value_semantics` **inference engine** (`ValueSemanticsEngine` with the value-typing modules
  in `demos/value_type_v2.py`) on the bundled raw crash CSV and writes `crashes_vsl.json`. The engine
  infers the flat event table deterministically for a fixed input and library versions.

**What this package does *not* let you rerun (and why):**
- **HR generation / inference.** The HR registry and raw data are withheld for privacy (§4), so HR
  cannot be regenerated externally. HR **per-case** material (case definitions, generated SQL, notes) is
  also withheld; only HR's **aggregate verdict labels** are retained, for the Table 2 totals.
- **Overhead measurements.** `vsl_overhead.json` holds the paper's saved local timings and retry rate.
  They **cannot be rerun from this ZIP**: `measure_vsl_overhead.py` iterates all configured domains
  (including the excluded HR registry) and needs the pre-generated comparison outputs for the per-query
  planning/validation timings, which are not shipped. It is included for reference only.
- **Registry *construction*.** All three registries were built by the `value_semantics` **inference
  engine** (§1): finance by Postgres profiling (`engine.infer_table`), HR from constructed table
  profiles, and public safety from the raw crash CSV (`demos/build_ps_registry_v2engine.py`). Only the
  **public-safety** registry can be rebuilt here (its builder + raw CSV are bundled). **Finance/HR
  registry construction cannot be rerun** from this ZIP: no raw BIRD database is bundled, and the HR data
  is withheld (§4).
  **Finance and public safety** are reproducible from the **shipped registry onward** (generation →
  Table 2); HR cannot be rerun because its registry is not shipped (§4). The engine is included
  (`value_semantics/`), and the finance build path is `value_semantics/cli/profile_postgres.py`.
- **Bit-identical outputs.** Generation uses `temperature = 0` — near-deterministic but not guaranteed
  identical across API versions/runs. Verdicts on reruns are assigned by whoever reruns, against the
  included rubric (`ADJUDICATION_RUBRIC.md`).

## 1. Provenance

- **Datasets.** Finance = BIRD. Public Safety = NYC Open Data, "Motor Vehicle Collisions — Crashes."
  HR = anonymized enterprise recruiting data; **raw records are not redistributed** (restrictions in §4).
- **Intents.** The evaluated cases come from the intent collection of the authors' formative study
  [`mahmud2026semanticgap`]; the intents were **constructed with LLM assistance**. The study collected
  **236 intents** across three domains; the evaluation selects **124** non-policy operationalization-failure
  cases, excluding 29 policy-grounding and 83 no-failure cases. The **finance and public-safety** case
  definitions are shipped (171 intents); **HR case definitions are withheld** (§4).
- **SQL generation.** All conditions use the same model (GPT-4o), identical decoding settings, and a
  single run per case.
- **Data-dictionary descriptions (D1 baseline).** Generated by GPT-4o from the schema via a frozen
  prompt that deliberately excludes operational semantics, then reviewed and corrected by the authors.
- **VST registries (PM/PE) — built by the inference engine.** **Finance** was built by the
  inference engine via Postgres profiling (`value_semantics/cli/profile_postgres.py`:
  `PostgresConnector.profile_table` → `ValueSemanticsEngine.infer_table` → `DatabaseSemanticsInferencer`).
  **HR** was built by the engine from constructed table profiles (`demos/build_hr_vsl.py` →
  `engine.infer_table`). **Public safety** was built by the engine from the raw crash CSV
  (`demos/build_ps_registry_v2engine.py`: `DataFrameProfiler` → `ValueSemanticsEngine.infer_table`, with
  the value-typing modules in `demos/value_type_v2.py`). All are automatically generated from
  per-column profiles (not hand-authored) and are consumed by the same planner/validator at query time.
- **Resolution labels.** Resolution labels were **assigned by the authors**, judging each generated
  query against its intent and expected behavior.
- **Audit / re-adjudication.** The authors, with AI assistance, reviewed the labels and generated
  SQL and identified a set of ground-truth issues; the authors then **re-judged** the affected cases,
  correcting eight condition-labels across six cases (`vsl_corrections_log.csv`). The criteria used
  are included (`ADJUDICATION_RUBRIC.md`).

## 2. Contents

| Item | File(s) |
|---|---|
| **VSL implementation** | `value_semantics/` (inference engine, planner, validator — importable package) |
| **Generation runners** | `run_vsl_benchmark_comparison.py` (baseline/PM/PE), `run_data_dictionary_baseline.py` (D1/D2), `generate_data_dictionary.py` (frozen D1 description prompt) |
| Dependencies | `requirements.txt` |
| Rubric / acceptance criteria | `ADJUDICATION_RUBRIC.md` |
| Generation prompts & decoding settings | `PROMPTS.md` |
| Licenses (this package + third-party) | `LICENSE.md` |
| **Final labels (authoritative, corrected)** | `nl2sql_results/vsl_final_labels.csv` |
| Correction log (original → corrected + reason) | `nl2sql_results/vsl_corrections_log.csv` |
| Original label sheets (SQL + per-case notes) — **finance & public safety only** | `nl2sql_results/vsl_human_evaluations_filled_v2.md`, `vsl_data_dictionary_human_eval_filled.md`, `vsl_vst_prose_human_eval.md` |
| Case definitions / categories | `{finance,public_safety}_benchmark_v2.json` (HR definitions withheld — see release note) |
| Author-reviewed data dictionaries (D1/D2 input) | `benchmarks/data_dictionary_finance.json`, `data_dictionary_public_safety.json` |
| Recomputation script | `recompute_vsl_eval.py` |
| Overhead (saved) | `nl2sql_results/vsl_overhead.json` (paper measurements); `measure_vsl_overhead.py` (reference only — not rerunnable here, see §3) |
| Public registries | `demos/bird_finance_vsl/`, `demos/public_safety_vsl/` |
| Raw data (public safety) | `demos/data/crashes_raw.csv` (NYC Open Data crash records, raw subset) |
| Registry builder (public safety) | `demos/build_ps_registry_v2engine.py` (inference engine: raw CSV → `crashes_vsl.json`); engine value-typing modules in `demos/value_type_v2.py` |

## 3. Reproduction vs. rerunning experiments

Run all commands from the bundle root (the runners put the root on `sys.path`).

```
# (a) Reproduce Table 2 from the supplied labels — no dependencies, no model, no database:
python3 benchmarks/recompute_vsl_eval.py

# (b) Rerun SQL generation (finance / public_safety) — needs deps + an API key, NO database.
#     Both runners make real model calls; run_data_dictionary_baseline defaults to a DRY RUN,
#     so pass --run for it. Note the different flags: --domain (singular) vs --domains (plural).
pip install -r requirements.txt
export OPENAI_API_KEY=...
python3 benchmarks/run_vsl_benchmark_comparison.py --domain finance          # baseline + PM + PE
python3 benchmarks/run_data_dictionary_baseline.py --run --domains finance    # D1 + D2

# (c) Rebuild the public-safety registry from the raw CSV with the inference engine (no DB/LLM).
#     By default it writes to a NEW dir so the shipped registry is preserved — then compare:
python3 demos/build_ps_registry_v2engine.py             # -> demos/public_safety_vsl_rebuilt/
diff demos/public_safety_vsl/crashes_vsl.json demos/public_safety_vsl_rebuilt/crashes_vsl.json
```

- **(a) `recompute_vsl_eval.py`** regenerates Table 2 from the supplied judgments
  (`vsl_final_labels.csv`). Python standard library only. It validates the label file (124 unique case
  IDs, a known category and a valid verdict for every case under all four conditions), computes the
  PM–PE gap from the data, and checks the computed totals against the paper's values.
- **(b) Rerunning SQL generation** loads the shipped JSON registries (`demos/bird_finance_vsl/`,
  `demos/public_safety_vsl/`) and the benchmark, infers nothing, and calls GPT-4o to generate the SQL
  for each condition — **no database is required**. Both runners make real model calls;
  `run_data_dictionary_baseline.py` **defaults to a dry run** (plan + token estimate only) and needs
  `--run` to execute. The D1/D2 baseline reads the **shipped author-reviewed data dictionaries**
  (`data_dictionary_{domain}.json`) — regenerating descriptions from scratch would not reproduce the
  original D1 inputs. Supported for `finance` and `public_safety`; `hr` will not run because the HR
  registry is withheld (§4). Mind the flags: `run_vsl_benchmark_comparison.py` uses `--domain`
  (singular), `run_data_dictionary_baseline.py` uses `--domains` (plural). The prompts/decoding settings
  (`PROMPTS.md`) are directly verifiable in the shipped runner code.
- **Automated judge disclosure.** `run_vsl_benchmark_comparison.py` also contains an automated GPT-4o
  **judge** that scores each generated query. **Its verdicts were *not* used for the paper's results** —
  the reported labels were **assigned by the authors** and audited (`ADJUDICATION_RUBRIC.md`,
  `vsl_corrections_log.csv`). The runner is shipped intact (faithful experiment code); a rerun yields
  fresh generated SQL, which should be judged against the rubric, not the automated verdicts.
- **(c) Rebuilding the public-safety registry.** `demos/build_ps_registry_v2engine.py` runs the
  `value_semantics` **inference engine** (`DataFrameProfiler` → `ValueSemanticsEngine.infer_table`, with
  the value-typing modules in `demos/value_type_v2.py`) on `demos/data/crashes_raw.csv`. By default
  it writes to `demos/public_safety_vsl_rebuilt/` (pass `--out-dir demos/public_safety_vsl` to rebuild in
  place), so the shipped registry is preserved for comparison. The engine profiles the first rows (not a
  random sample), so it is deterministic for a fixed input and library versions (`index.json` embeds the
  output path, so it differs by the `--out-dir` prefix; other library versions can produce small
  numeric-formatting differences in stored sample values). The finance and HR registries cannot be
  rebuilt here (no raw BIRD database; HR data withheld — §0).
- **Overhead is not rerunnable from this ZIP.** See §0: `vsl_overhead.json` is the saved paper
  measurement; `measure_vsl_overhead.py` is reference only (it iterates all domains including the
  excluded HR one, needs unshipped comparison outputs, and would overwrite `vsl_overhead.json`).

## 4. Licenses & restrictions

Full text and the MIT license body are in **`LICENSE.md`**. In short:

- **This package's own material:** code under **MIT** (the `value_semantics/` implementation, the
  generation runners, and the evaluation/recompute scripts); our original data and documents (labels,
  corrections log, rubric, `PROMPTS.md`, intents/case definitions, author-reviewed data dictionaries,
  public-safety VST registry) under **CC BY 4.0** — the authors' confirmed licenses for this release.
  Full text in `LICENSE.md`.
- **Finance (BIRD):** CC BY-SA 4.0 — redistribution permitted **with attribution** to BIRD and under
  the **same share-alike license**; the BIRD-derived portion of this package is released under
  CC BY-SA 4.0. Source/license: https://bird-bench.github.io/ (verified 2026-10-26: BIRD states
  CC BY-SA 4.0, a change the maintainers made on 2024-04-27).
- **Public Safety (NYC Open Data):** the dataset is NYC Open Data's **"Motor Vehicle Collisions —
  Crashes"** (dataset `h9gi-nx95`), open under NYC's Open Data policy (Local Law 11 of 2012) with no
  license/registration/use restriction; redistribution may be required to **identify source, version,
  and any modifications**. We identify the source and modifications (single-table subset for VST
  inference); the specific **version/retrieval date was not recorded** (see `LICENSE.md`). Source:
  https://opendata.cityofnewyork.us/ · policy: https://opendata.cityofnewyork.us/open-data-law/
  (verified 2026-10-26).
- **HR:** anonymized enterprise recruiting data — **raw records are not included, the HR
  registry/profiles (`demos/hr_vsl/`) are not part of the release, and HR per-case material (case
  definitions, generated SQL, and per-case notes) is withheld.** The reversible de-anonymization maps are
  likewise excluded. Only HR's **aggregate verdict labels** (`domain`, `category`, and the four condition
  verdicts in `vsl_final_labels.csv`) are retained — these carry no schema, SQL, or data. This withholding
  is the authors' own, documented in the internal permissions checklist; it is not a third-party
  certification.
- **Intents:** from the authors' own formative study [`mahmud2026semanticgap`]; redistributed by the
  authors, so there is no third-party restriction.

**Attribution (shipped with the release):**
- Finance data derived from the **BIRD** benchmark (Li et al., 2023), https://bird-bench.github.io/,
  used under **CC BY-SA 4.0**; the BIRD-derived portion of this package is released under CC BY-SA 4.0.
- Public-safety data from **NYC Open Data, "Motor Vehicle Collisions — Crashes"** (City of New York,
  dataset `h9gi-nx95`), https://opendata.cityofnewyork.us/, subset and reformatted for this evaluation
  (single-table subset). The raw subset is shipped as `demos/data/crashes_raw.csv` under the same terms.
  Source and modifications are identified per Local Law 11 of 2012; the specific dataset version/retrieval
  date was not recorded.

**Not included in the release:** `demos/hr_vsl/` (HR registry, profiles, and the de-anonymization /
id-map files), any HR raw records, **HR per-case material** (`hr_benchmark_v2.json`, the HR sections of the
human-eval sheets, and HR rows of the corrections log), the one-time label-build script
(`build_final_labels.py`), the raw BIRD source database (the NYC crash raw subset **is** included as
`demos/data/crashes_raw.csv`), the pre-generated comparison outputs (regenerable via §3(b); they also
contain the unused automated-judge fields), and the internal working documents (`AUDIT_SUMMARY.md`,
`ACCEPTANCE_CRITERIA.md`, `PERMISSIONS_CHECKLIST.md`).

## 5. Limitations

- A **curated diagnostic subset** targeting value-semantics failures — not a neutral/general NL2SQL
  benchmark; it measures whether VSL helps on these failure modes, not general superiority.
- **Single run per case**, **GPT-4o only**, **one agent** (Blue NL2SQL); the planner intervention is
  bundled (planning + validation) and does not isolate enforcement alone.
- Rerunning generation is supported for **finance and public safety only**; HR cannot be rerun (its
  registry and data are withheld). Only the public-safety registry can be rebuilt here (byte-exact only
  under the pinned library versions); finance/HR registry construction is not reproducible from this ZIP
  (see §0).
- **PE intent patterns overlap the evaluated phrasings (possible evaluation leakage).** The PE prototype
  uses domain-specific intent patterns (in `value_semantics/vst/planner.py`), some of which overlap with
  the evaluated query phrasings. The extent to which individual evaluation cases influenced rule
  development is not established; generalization to unseen formulations remains untested. This concerns
  PE only — the prompt-mediated (PM) condition does not use these planner rules.
- **Overhead measurements are saved, not rerunnable** from this ZIP (`measure_vsl_overhead.py` needs the
  excluded HR registry and the unshipped comparison outputs; see §3).
- The ground-truth adjudication covered the **flagged** cases, condition-consistently; a complete
  independent re-judgment of all 124 was not performed.
- Resolution labels were assigned by the authors; a subset were re-judged by the authors against a
  consistent set of criteria, with issues surfaced by AI-assisted analysis (§1). No blinding,
  inter-annotator agreement, or variance is claimed.
