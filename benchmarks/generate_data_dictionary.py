#!/usr/bin/env python3
"""
Generate the D1 data-dictionary baseline (frozen) for the VSL "beyond descriptions" ablation.

For each column it produces a SHORT, catalog-style business DESCRIPTION (what the column IS:
meaning, unit, entity, a representative example) and DELIBERATELY EXCLUDES operational semantics
(thresholds, "unusual" cutoffs, per-group stats, safe/forbidden aggregation, identifier-as-rule,
temporal-persistence rules) — those are exactly what VSTs add; leaking them would contaminate the
baseline. A hand-curation pass follows generation (see BASELINE_SCOPING.md).

SAFETY: defaults to --dry-run (prints prompts + token estimate, NO API call). Pass --run to
actually call the model. Output: benchmarks/data_dictionary_<domain>.json  {"table.col": "desc"}.

Frozen 2026-10-14. Do not edit the GEN_PROMPT after the dictionaries are frozen/SHA-pinned.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path


def _load_env(repo: Path):
    """Best-effort: load KEY=VALUE lines from .env into os.environ (no values printed)."""
    envf = repo / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

DOMAINS = {
    "finance":       "demos/bird_finance_vsl",
    # hr withheld from public release (see README)
    "public_safety": "demos/public_safety_vsl",
}

# ---- FROZEN generation prompt -------------------------------------------------
SYSTEM = (
    "You are a data steward writing a column-level data dictionary for a SQL database. "
    "You produce accurate, concise business descriptions a BI catalog would contain."
)
# --style with_examples : realistic catalog entry (meaning + unit + a representative example)
GEN_PROMPT_WITH_EXAMPLES = """\
Write a one-sentence business description for EACH column of the table below.

DESCRIBE (what the column is):
  - its business meaning, the real-world entity/event it belongs to,
  - its unit or format if applicable, and a representative example value.

DO NOT state any of the following (these are out of scope for a plain data dictionary):
  - numeric thresholds, "unusual"/outlier cutoffs, min/max bounds, or percentile statistics,
  - per-group or distribution-dependent rules,
  - which aggregations are safe or forbidden (e.g. "do not sum"), or identifier-as-a-rule phrasing,
  - temporal-persistence / "sustained" rules or time-bucketing requirements.
Keep each description purely descriptive, <= 25 words, no SQL.

Table: {table}
Columns (name : type : example values):
{columns}

Return ONLY a JSON object mapping each column name to its description string:
{{"col_a": "...", "col_b": "..."}}
"""

# --style description_only : reviewer-faithful (R3-W4) — pure meaning, NO example values / stats
# mirrors the reviewer's example: "balance: the account balance after each transaction"
GEN_PROMPT_DESCRIPTION_ONLY = """\
Write a one-sentence business description for EACH column of the table below, in the exact
style of a data-catalog entry such as: "balance: the account balance after each transaction".

Give ONLY the column's business meaning and the real-world entity/event it belongs to.

DO NOT include any of the following:
  - example or sample values of any kind,
  - numeric ranges, min/max, statistics, or data types,
  - thresholds, outlier/"unusual" cutoffs, or distribution-dependent rules,
  - aggregation rules ("do not sum"), identifier-as-a-rule phrasing,
  - temporal-persistence / time-bucketing rules.
Keep each description a short plain-meaning phrase, <= 18 words, no example values, no SQL.

Table: {table}
Columns (name : type : example values are provided only to help you identify the column — do NOT repeat them):
{columns}

Return ONLY a JSON object mapping each column name to its description string:
{{"col_a": "...", "col_b": "..."}}
"""

GEN_PROMPTS = {"with_examples": GEN_PROMPT_WITH_EXAMPLES,
               "description_only": GEN_PROMPT_DESCRIPTION_ONLY}


def load_tables(domain_dir: str):
    """Return [(table_name, {col: {declared_type, sample_values}})] from per-table *_vsl.json."""
    idx = json.load(open(os.path.join(domain_dir, "index.json")))
    out = []
    for t in idx["tables"]:
        p = t["path"]
        fp = p if os.path.exists(p) else os.path.join(domain_dir, os.path.basename(p))
        tj = json.load(open(fp))
        cols = tj.get("columns") or {}
        if isinstance(cols, list):  # defensive
            cols = {c.get("name", f"c{i}"): c for i, c in enumerate(cols)}
        out.append((tj.get("table") or t.get("table"), cols))
    return out


def fmt_columns(cols: dict) -> str:
    lines = []
    for name, meta in cols.items():
        typ = meta.get("declared_type", "?") if isinstance(meta, dict) else "?"
        samp = meta.get("sample_values", []) if isinstance(meta, dict) else []
        samp = ", ".join(str(x) for x in samp[:5])
        lines.append(f"  {name} : {typ} : {samp}")
    return "\n".join(lines)


def est_tokens(s: str) -> int:
    return max(1, len(s) // 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="actually call the model (default: dry-run)")
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--domains", nargs="*", default=list(DOMAINS))
    ap.add_argument("--style", choices=list(GEN_PROMPTS), default="description_only",
                    help="description_only (reviewer-faithful, primary) or with_examples (D1b)")
    args = ap.parse_args()
    gen_prompt = GEN_PROMPTS[args.style]
    suffix = "" if args.style == "description_only" else "_with_examples"

    repo = Path(__file__).resolve().parents[1]
    os.chdir(repo)
    _load_env(repo)

    engine = None
    if args.run:
        from value_semantics.nl2sql.nl2sql_engine import NL2SQLEngine
        engine = NL2SQLEngine(provider=args.provider, model=args.model)

    grand_in = grand_out = grand_cols = 0
    for dom in args.domains:
        ddir = DOMAINS[dom]
        tables = load_tables(ddir)
        n_cols = sum(len(c) for _, c in tables)
        grand_cols += n_cols
        print(f"\n=== {dom}: {len(tables)} tables, {n_cols} columns ===")
        result: dict[str, str] = {}
        for tname, cols in tables:
            prompt = gen_prompt.format(table=tname, columns=fmt_columns(cols))
            in_tok = est_tokens(SYSTEM + prompt)
            out_tok = 20 * len(cols)  # ~20 tok/description
            grand_in += in_tok; grand_out += out_tok
            if not args.run:
                if tname == tables[0][0]:  # show one example prompt per domain
                    print(f"--- example prompt ({tname}) ---\n{prompt}\n--- (~{in_tok} in / ~{out_tok} out tok) ---")
                continue
            raw = engine._provider.complete(SYSTEM, prompt)
            txt = raw[raw.find("{"): raw.rfind("}") + 1]
            try:
                desc = json.loads(txt)
            except Exception:
                print(f"  !! parse failed for {tname}; raw head: {raw[:120]}")
                desc = {}
            for col, d in desc.items():
                result[f"{tname}.{col}"] = d
        if args.run:
            outp = f"benchmarks/data_dictionary_{dom}{suffix}.json"
            json.dump(result, open(outp, "w"), indent=2)
            print(f"  wrote {outp}  ({len(result)} descriptions)")

    # rough cost: gpt-4o $2.50/1M in, $10/1M out
    cost = grand_in / 1e6 * 2.50 + grand_out / 1e6 * 10.0
    mode = "RUN" if args.run else "DRY-RUN (no API calls made)"
    print(f"\n[{mode}] total columns={grand_cols}  est_input≈{grand_in} tok  est_output≈{grand_out} tok  est_cost≈${cost:.3f}")
    if not args.run:
        print("Re-run with --run to generate (after approval). Then hand-curate + freeze.")


if __name__ == "__main__":
    main()
