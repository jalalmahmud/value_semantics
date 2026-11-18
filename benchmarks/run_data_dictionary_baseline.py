#!/usr/bin/env python3
"""
Run the D1 (data_dictionary) and D2 (vst_prose) baseline conditions on the SAME 124 cases.

Additive & non-destructive: does NOT touch baseline / prompt_mediated / planner_enforced. Reuses
the published runner's judge, schema loader, and VST registry so judging is identical. Baseline/PM/PE
verdicts for the combined table are READ from the latest existing automated run (same judge model
gpt-4o, same vst_summary context) — they are directional/superseded; the authoritative comparison is
the human eval (Gate 3).

  D1 data_dictionary : schema + frozen catalog-style column descriptions (no operational facts)
  D2 vst_prose       : schema + the SAME VST facts as PM, rendered as neutral descriptive prose
                       (no imperative directives / flags / "use to guide generation" framing)

SAFETY: defaults to --dry-run (plan + token estimate, NO API calls). Pass --run to execute.
Frozen 2026-10-15.
"""
from __future__ import annotations
import argparse, json, os, sys, time, glob
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import run_vsl_benchmark_comparison as R
from value_semantics.nl2sql.sql_extractor import extract_sql
from value_semantics.nl2sql.prompt_builder import build_schema_text, SYSTEM_PROMPT

DICT_PATH = {d: REPO / f"benchmarks/data_dictionary_{d}.json" for d in R.DOMAIN_CONFIG}


def _load_env():
    envf = REPO / ".env"
    if not envf.exists():
        return
    for line in envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---- D1: data-dictionary condition --------------------------------------------
def build_dictionary_hint_text(dictionary: dict) -> str:
    lines = ["COLUMN DESCRIPTIONS (data dictionary):"]
    for col, desc in dictionary.items():
        lines.append(f"  {col}: {desc}")
    return "\n".join(lines)


def generate_data_dictionary(engine, question, schema, dictionary) -> str:
    prompt = (
        f"Database schema:\n```sql\n{build_schema_text(schema)}\n```\n\n"
        f"{build_dictionary_hint_text(dictionary)}\n\n"
        f"Question: {question}\n\n"
        f"Write a SQL query that answers the question using the schema and column descriptions above.\n"
        f"Return only a ```sql code block."
    )
    return extract_sql(engine._provider.complete(SYSTEM_PROMPT, prompt))


# ---- D2: information-matched prose (same facts as build_vst_hint_text) ---------
def build_vst_prose_text(registry) -> str:
    """Render the SAME VST facts PM uses, as neutral declarative prose (no imperatives/flags)."""
    lines = ["COLUMN NOTES (descriptive):"]
    planner = R.VSLPlanner()
    for vst in registry.all_vsts():
        clauses = []
        if vst.semantic_role:
            clauses.append(f"serves the role of {vst.semantic_role}")
        if vst.process_role:
            clauses.append(f"participates as {vst.process_role} within a process")
        if vst.is_identifier:
            clauses.append("is an identifier value")
        if vst.should_not_sum:
            clauses.append("holds values that are not meaningfully additive")
        if vst.requires_temporal_context:
            clauses.append("is interpretable only within a temporal context")
        if vst.supports_outlier_detection:
            t = planner._extract_thresholds(vst)
            if t:
                clauses.append(f"has a 90th-percentile value of approximately {t['p90']}")
        if vst.derived_metrics:
            dm = vst.derived_metrics[0]
            clauses.append(f"relates to the derived metric {dm.get('formula_template','')}")
        if clauses:
            lines.append(f"  {vst.table}.{vst.column} " + "; ".join(clauses) + ".")
    return "\n".join(lines)


def generate_vst_prose(engine, question, schema, registry) -> str:
    prompt = (
        f"Database schema:\n```sql\n{build_schema_text(schema)}\n```\n\n"
        f"{build_vst_prose_text(registry)}\n\n"
        f"Question: {question}\n\n"
        f"Write a SQL query that answers the question using the schema and column notes above.\n"
        f"Return only a ```sql code block."
    )
    return extract_sql(engine._provider.complete(SYSTEM_PROMPT, prompt))


# ---- reuse existing baseline/PM/PE verdicts -----------------------------------
def load_prior_verdicts(domain: str) -> dict:
    cands = sorted(glob.glob(str(REPO / f"benchmarks/nl2sql_results/vsl_comparison_{domain}_openai_gpt-4o_*.json")))
    cands = [c for c in cands if "summary" not in c and "combined" not in c]
    if not cands:
        return {}
    d = json.load(open(cands[-1]))
    out = {}
    for r in d["results"]:
        out[r["id"]] = {k: r[k].get("verdict") for k in ("baseline", "prompt_mediated", "planner_enforced") if k in r}
    return out


def tally(rows, key):
    n = len(rows)
    c = sum(1 for r in rows if r[key] == "correct")
    p = sum(1 for r in rows if r[key] == "partial")
    i = sum(1 for r in rows if r[key] == "incorrect")
    g = round((c + p) / n, 3) if n else 0
    return dict(n=n, fully=c, partial=p, unresolved=i, grounding=g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="execute (default: dry-run)")
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--domains", nargs="*", default=list(R.DOMAIN_CONFIG))
    args = ap.parse_args()
    os.chdir(REPO)
    _load_env()

    engine = None
    if args.run:
        engine = R.NL2SQLEngine(provider=args.provider, model=args.model)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    all_rows = []
    total_cases = 0

    for dom in args.domains:
        cfg = R.DOMAIN_CONFIG[dom]
        # match the published Table 1: 124 NON-POLICY failures (exclude "none" + "policy_grounding")
        bench = [q for q in R.load_benchmark(cfg["benchmark"])
                 if q.get("category", "none") not in ("none", "policy_grounding")]
        total_cases += len(bench)
        schema = R.load_schema(cfg["schema"])
        registry = R.VSTRegistry.from_vsl_dir(cfg["vsl_dir"])
        vst_summary = R.build_vst_summary(registry, "")
        dictionary = json.load(open(DICT_PATH[dom]))
        prior = load_prior_verdicts(dom)
        print(f"\n=== {dom}: {len(bench)} cases | dict={len(dictionary)} cols | prior_verdicts={len(prior)} ===")

        if not args.run:
            print(f"  [dry-run] would generate D1+D2 ({2*len(bench)} gens) and judge ({2*len(bench)} judge calls)")
            continue

        dom_rows = []
        for i, q in enumerate(bench, 1):
            qid, question, cat = q["id"], q["intent"], q.get("category", "unknown")
            exp = q.get("expected_behavior", "")
            try:
                d1_sql = generate_data_dictionary(engine, question, schema, dictionary)
            except Exception as e:
                d1_sql = f"ERROR: {e}"
            try:
                d2_sql = generate_vst_prose(engine, question, schema, registry)
            except Exception as e:
                d2_sql = f"ERROR: {e}"
            time.sleep(0.4)
            d1_v = R.judge_sql(engine, question, cat, exp, d1_sql, vst_summary)
            time.sleep(0.3)
            d2_v = R.judge_sql(engine, question, cat, exp, d2_sql, vst_summary)
            time.sleep(0.3)
            row = {
                "id": qid, "domain": dom, "category": cat,
                "data_dictionary": d1_v.get("verdict"),
                "vst_prose": d2_v.get("verdict"),
                "data_dictionary_sql": d1_sql, "vst_prose_sql": d2_sql,
                "data_dictionary_reason": d1_v.get("reason"),
                "vst_prose_reason": d2_v.get("reason"),
            }
            row.update(prior.get(qid, {}))
            dom_rows.append(row)
            print(f"  [{i:3}/{len(bench)}] {qid} ({cat}): D1={row['data_dictionary']:9s} D2={row['vst_prose']:9s}")

        out = REPO / f"benchmarks/nl2sql_results/vsl_dd_baseline_{dom}_{args.provider}_{args.model}_{ts}.json"
        json.dump({"run_at": ts, "model": args.model, "domain": dom, "results": dom_rows}, open(out, "w"), indent=2)
        print(f"  wrote {out.name}")
        all_rows.extend(dom_rows)

    if not args.run:
        print(f"\n[DRY-RUN] {total_cases} cases → {2*total_cases} gens + {2*total_cases} judge calls. Re-run with --run.")
        return

    # combined automated table (5 conditions)
    combined = REPO / f"benchmarks/nl2sql_results/vsl_dd_baseline_combined_{ts}.json"
    json.dump({"run_at": ts, "total": len(all_rows), "results": all_rows}, open(combined, "w"), indent=2)
    conds = ["baseline", "data_dictionary", "vst_prose", "prompt_mediated", "planner_enforced"]
    print(f"\n{'='*72}\nAUTOMATED FIRST PASS (gpt-4o self-judge; directional) — n={len(all_rows)}\n{'='*72}")
    print(f"{'condition':20s} {'fully':>6s} {'partial':>8s} {'unres':>6s} {'grounding':>10s}")
    present = [c for c in conds if all(c in r for r in all_rows)]
    for c in conds:
        if c not in present:
            print(f"{c:20s} {'(no prior verdicts found)':>34s}")
            continue
        t = tally(all_rows, c)
        print(f"{c:20s} {t['fully']:6d} {t['partial']:8d} {t['unresolved']:6d} {t['grounding']:10.1%}")
    print(f"\nwrote {combined.name}")


if __name__ == "__main__":
    main()
