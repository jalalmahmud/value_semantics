# Licenses

This package mixes the authors' own material with third-party-derived data. Different parts carry
different licenses; this file states which applies to what.

## This package's own material (authored by us)

- **Code** — the `value_semantics/` implementation (inference engine, planner, validator), the
  generation runners (`run_vsl_benchmark_comparison.py`, `run_data_dictionary_baseline.py`,
  `generate_data_dictionary.py`), the public-safety registry builder
  (`demos/build_public_safety_vsl.py`), and the evaluation/recompute scripts (`recompute_vsl_eval.py`, `measure_vsl_overhead.py`): **MIT License**.
- **Original data and documents** we authored — the labels (`vsl_final_labels.csv`,
  `vsl_corrections_log.csv`), the rubric (`ADJUDICATION_RUBRIC.md`), the prompt documentation
  (`PROMPTS.md`), the benchmark intents/case definitions, the author-reviewed data dictionaries
  (`benchmarks/data_dictionary_{finance,public_safety}.json`), and the public-safety VST registry
  (`demos/public_safety_vsl/`): **CC BY 4.0**.

These are the authorized licenses for this release (code MIT, our data CC BY 4.0). Copyright holder for
both: **Megagon Labs** (2026). Attribution for the CC BY 4.0 material: "Megagon Labs (2026)."

## Third-party-derived material

- **Finance (BIRD-derived):** the BIRD benchmark is released under **CC BY-SA 4.0** (the BIRD maintainers
  changed the dataset license to CC BY-SA 4.0 on 2024-04-27). Because CC BY-SA 4.0 is **share-alike**,
  the BIRD-derived files in this package are released under **CC BY-SA 4.0**, with attribution to BIRD.
  **Share-alike applies specifically to:** all files under `demos/bird_finance_vsl/` — namely
  `account_vsl.json`, `card_vsl.json`, `client_vsl.json`, `database_vsl.json`, `disp_vsl.json`,
  `district_vsl.json`, `loan_vsl.json`, `order_vsl.json`, `trans_vsl.json`, `index.json`, and
  `policy_definitions.json` (schema and value profiles derived from BIRD's finance database). Our own
  finance **intents, generated SQL, and labels** describe the BIRD data but are original annotations
  authored by us (CC BY 4.0); any verbatim BIRD content they quote remains under CC BY-SA 4.0.
  Source / license: https://bird-bench.github.io/
- **Public Safety (NYC Open Data):** derived from NYC Open Data's **"Motor Vehicle Collisions —
  Crashes"** dataset (dataset `h9gi-nx95`), published under the City of New York's Open Data policy
  pursuant to **Local Law 11 of 2012**. NYC Open Data imposes no license, registration, or use
  restriction, but permits requiring that redistribution **identify the source, version, and any
  modifications**. We subset and reformatted the data for this evaluation (modification: single-table
  subset). We ship **both** the raw subset (`demos/data/crashes_raw.csv`) and the derived value-profile
  registry (`demos/public_safety_vsl/`), under these NYC terms. **Version / retrieval date:** not
  recorded in this package (the data shows crash dates around 2023, but the specific portal
  snapshot/version was not recorded). Source: https://opendata.cityofnewyork.us/ · policy:
  https://opendata.cityofnewyork.us/open-data-law/
- **Intents:** from the authors' own formative study (`mahmud2026semanticgap`); redistributed by the
  authors, so there is no third-party redistribution restriction. The intents were constructed with LLM
  assistance.

## MIT License (for the code above)

```
Copyright (c) 2026 Megagon Labs

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
