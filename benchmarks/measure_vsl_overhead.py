#!/usr/bin/env python3
"""
Measure the VSL-specific computational overhead (R1-O7) — NO LLM calls.
Times registry load, per-query planning (retrieval + intent classify + constraint build), and
per-query validation (sqlglot parse + VST rule checks) over the 124 non-policy cases, and reports
the PE rejection-loop retry stats from saved results.
"""
from __future__ import annotations
import glob, json, statistics, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "benchmarks"))
import run_vsl_benchmark_comparison as R
from value_semantics.vst.registry import VSTRegistry
from value_semantics.vst.policy import PolicyRegistry
from value_semantics.vst.planner import VSLPlanner
from value_semantics.vst.validator import VSTValidator
from value_semantics.nl2sql.prompt_builder import build_schema_text

REPS = 7  # per-case repeats; take median to reduce noise


def med_ms(fn):
    ts = []
    for _ in range(REPS):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
    return statistics.median(ts)


def latest(dom):
    c = [f for f in glob.glob(str(REPO / f"benchmarks/nl2sql_results/vsl_comparison_{dom}_openai_gpt-4o_*.json"))
         if "summary" not in f and "combined" not in f]
    return json.load(open(sorted(c)[-1])) if c else None


def main():
    planner, validator = VSLPlanner(), VSTValidator()
    reg_load, plan_ms, val_ms, retries = {}, [], [], []
    n_cases = 0
    for dom, cfg in R.DOMAIN_CONFIG.items():
        schema = R.load_schema(cfg["schema"]); schema_text = build_schema_text(schema)
        dt = cfg.get("default_table")
        reg_load[dom] = med_ms(lambda: (VSTRegistry.from_vsl_dir(cfg["vsl_dir"]),
                                        PolicyRegistry.from_vsl_dir(cfg["vsl_dir"])))
        registry = VSTRegistry.from_vsl_dir(cfg["vsl_dir"])
        policy = PolicyRegistry.from_vsl_dir(cfg["vsl_dir"])
        data = latest(dom)
        if not data:
            continue
        for r in data["results"]:
            if r.get("category") in (None, "none", "policy_grounding"):
                continue
            n_cases += 1
            q = r["intent"]; sql = (r.get("planner_enforced") or {}).get("sql") or ""
            plan_ms.append(med_ms(lambda: planner.plan(question=q, schema_text=schema_text,
                                                        registry=registry, policy_registry=policy)))
            if sql and not sql.startswith("ERROR"):
                val_ms.append(med_ms(lambda: validator.validate(sql, registry, default_table=dt)))
            retries.append(r.get("planner_retries", 0) or 0)

    def stats(xs):
        xs = sorted(xs)
        return (statistics.mean(xs), statistics.median(xs), xs[int(0.95 * len(xs)) - 1]) if xs else (0, 0, 0)

    pm, pmed, p95 = stats(plan_ms); vm, vmed, v95 = stats(val_ms)
    print(f"cases: {n_cases}  (validation timed on {len(val_ms)} non-error SQL)\n")
    print("registry load (one-time per DB), ms:")
    for d, t in reg_load.items():
        print(f"  {d:14s} {t:6.1f} ms  ({len(VSTRegistry.from_vsl_dir(R.DOMAIN_CONFIG[d]['vsl_dir']).all_vsts())} VSTs)")
    print(f"\nper-query PLANNING (retrieval+intent+constraints): mean {pm:.2f} ms, median {pmed:.2f}, p95 {p95:.2f}")
    print(f"per-query VALIDATION (sqlglot parse+rule checks):  mean {vm:.2f} ms, median {vmed:.2f}, p95 {v95:.2f}")
    print(f"per-query VSL OVERHEAD (plan+validate), median:    {pmed + vmed:.2f} ms")
    nz = [x for x in retries if x > 0]
    print(f"\nPE rejection loop: {len(nz)}/{len(retries)} = {len(nz)/max(1,len(retries)):.0%} of cases triggered "
          f">=1 retry; mean retries {statistics.mean(retries):.2f}, max {max(retries) if retries else 0}")
    json.dump({"n_cases": n_cases, "registry_load_ms": reg_load,
               "plan_ms": {"mean": pm, "median": pmed, "p95": p95},
               "validate_ms": {"mean": vm, "median": vmed, "p95": v95},
               "retry_rate": len(nz)/max(1,len(retries)), "mean_retries": statistics.mean(retries) if retries else 0},
              open(REPO / "benchmarks/nl2sql_results/vsl_overhead.json", "w"), indent=2)
    print("\nwrote benchmarks/nl2sql_results/vsl_overhead.json")


if __name__ == "__main__":
    main()
