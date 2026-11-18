"""
VSL Three-Way Benchmark Comparison
====================================
Controlled apples-to-apples comparison of three SQL generation approaches
on exactly the same set of semantic failure cases.

Systems:
  baseline          — schema-only prompt, no VST (LLM baseline)
  prompt_mediated   — schema + all VST metadata dumped as text hints (v2 approach)
  planner_enforced  — VST planner: intent-classified, grounded constraints + rejection loop

Evaluation:
  LLM-as-judge (GPT-4o) evaluates each generated SQL against the question's
  expected_behavior and semantic category. Verdict: correct / partial / incorrect.

Output:
  benchmarks/nl2sql_results/vsl_comparison_finance_<timestamp>.json  (per-question)
  benchmarks/vsl_comparison_finance_summary.json                     (3-way table)

Usage:
    python benchmarks/run_vsl_benchmark_comparison.py \\
        --provider openai --model gpt-4o --domain finance
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from value_semantics.nl2sql import NL2SQLEngine
from value_semantics.nl2sql.vsl_schema_loader import load_schema
from value_semantics.nl2sql.prompt_builder import build_schema_text, SYSTEM_PROMPT
from value_semantics.vst import VSTRegistry, VSLPlanner
from value_semantics.vst.policy import PolicyRegistry

DOMAIN_CONFIG = {
    "finance": {
        "benchmark": "benchmarks/finance_benchmark_v2.json",
        "schema": "demos/bird_finance_vsl/index.json",
        "vsl_dir": "demos/bird_finance_vsl",
        "default_table": None,
    },
    # HR domain withheld from the public release (HR data proprietary; see README release note).
    "public_safety": {
        "benchmark": "benchmarks/public_safety_benchmark_v2.json",
        "schema": "demos/public_safety_vsl/index.json",
        "vsl_dir": "demos/public_safety_vsl",
        "default_table": "crashes",
    },
}

# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = """\
You are an expert SQL evaluator specialising in semantic correctness.
Given a natural language question, its semantic category, expected behavior,
and a generated SQL query, evaluate:

1. Does the SQL answer the question correctly?
2. Does it use semantically appropriate patterns (right thresholds, temporal
   structure, correct column roles)?

Respond with a JSON object ONLY — no explanation outside the JSON:
{
  "verdict": "correct" | "partial" | "incorrect",
  "reason": "<1-2 sentence explanation>",
  "semantic_issues": ["list of specific semantic problems, or empty list if none"]
}

Verdict definitions:
  correct   — SQL fully answers the question with correct semantics
  partial   — SQL partially answers or has minor semantic issues
  incorrect — SQL misses the semantic requirement or gives a wrong answer
"""


def judge_sql(
    engine: NL2SQLEngine,
    question: str,
    category: str,
    expected_behavior: str,
    sql: str,
    vst_summary: str,
) -> dict:
    prompt = f"""\
QUESTION: {question}

CATEGORY: {category}

EXPECTED BEHAVIOR: {expected_behavior}

VST SEMANTIC CONTEXT:
{vst_summary}

GENERATED SQL:
```sql
{sql or "(empty)"}
```

Evaluate and return JSON only."""

    try:
        raw = engine._provider.complete(JUDGE_SYSTEM, prompt)
        # Extract JSON from response
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        pass
    return {"verdict": "error", "reason": str(engine), "semantic_issues": []}


def build_vst_summary(registry: VSTRegistry, question: str) -> str:
    """Build a concise VST context for the judge (not for the generator)."""
    lines = []
    for vst in registry.all_vsts():
        if vst.is_identifier:
            lines.append(f"  {vst.table}.{vst.column}: IDENTIFIER (no magnitude ordering)")
        elif vst.requires_temporal_context:
            lines.append(f"  {vst.table}.{vst.column}: {vst.process_role} (requires temporal aggregation)")
        elif vst.should_not_sum:
            lines.append(f"  {vst.table}.{vst.column}: {vst.semantic_role} (SUM forbidden)")
        elif vst.supports_outlier_detection:
            t = VSLPlanner()._extract_thresholds(vst)
            thresh = f", p90≈{t['p90']}" if t else ""
            lines.append(f"  {vst.table}.{vst.column}: measure with outlier detection{thresh}")
    return "\n".join(lines[:20])  # cap to keep judge prompt manageable


# ---------------------------------------------------------------------------
# Prompt-mediated VST generation (v2 approach)
# ---------------------------------------------------------------------------

def build_vst_hint_text(registry: VSTRegistry) -> str:
    """Build full VST metadata text for prompt-mediated approach."""
    lines = ["VALUE SEMANTIC METADATA (use to guide SQL generation):"]
    for vst in registry.all_vsts():
        parts = [f"{vst.table}.{vst.column}"]
        if vst.semantic_role:
            parts.append(f"role={vst.semantic_role}")
        if vst.process_role:
            parts.append(f"process={vst.process_role}")
        if vst.is_identifier:
            parts.append("IDENTIFIER: do not aggregate or compare magnitudes")
        if vst.should_not_sum:
            parts.append("should_not_sum=True")
        if vst.requires_temporal_context:
            parts.append("requires_temporal_context=True")
        if vst.supports_outlier_detection:
            t = VSLPlanner()._extract_thresholds(vst)
            if t:
                parts.append(f"outlier_p90={t['p90']}")
        if vst.derived_metrics:
            dm = vst.derived_metrics[0]
            parts.append(f"derived_metric={dm.get('formula_template','')}")
        lines.append("  " + " | ".join(parts))
    return "\n".join(lines)


def generate_prompt_mediated(
    engine: NL2SQLEngine,
    question: str,
    schema: dict,
    registry: VSTRegistry,
) -> str:
    schema_text = build_schema_text(schema)
    vst_hints = build_vst_hint_text(registry)
    prompt = (
        f"Database schema:\n```sql\n{schema_text}\n```\n\n"
        f"{vst_hints}\n\n"
        f"Question: {question}\n\n"
        f"Write a SQL query that answers the question using the semantic guidance above.\n"
        f"Return only a ```sql code block."
    )
    from value_semantics.nl2sql.sql_extractor import extract_sql
    raw = engine._provider.complete(SYSTEM_PROMPT, prompt)
    return extract_sql(raw)


# ---------------------------------------------------------------------------
# Per-question evaluation
# ---------------------------------------------------------------------------

def evaluate_question(
    q: dict,
    engine: NL2SQLEngine,
    schema: dict,
    registry: VSTRegistry,
    planner: VSLPlanner,
    vst_summary: str,
    policy_registry: PolicyRegistry = None,
) -> dict:
    question = q["intent"]
    category = q.get("category", "unknown")
    expected = q.get("expected_behavior", "")

    results = {}

    # 1. Baseline
    try:
        base = engine.generate(question=question, schema=schema)
        baseline_sql = base.sql
    except Exception as e:
        baseline_sql = f"ERROR: {e}"

    # 2. Prompt-mediated
    try:
        pm_sql = generate_prompt_mediated(engine, question, schema, registry)
    except Exception as e:
        pm_sql = f"ERROR: {e}"

    # 3. Planner-enforced
    try:
        plan_result = engine.generate_with_planner(
            question=question,
            schema=schema,
            vst_registry=registry,
            max_retries=2,
            policy_registry=policy_registry,
        )
        planner_sql = plan_result.sql
        detected_intent = plan_result.vsl_plan.intent.value if plan_result.vsl_plan else "unknown"
        retries = plan_result.vsl_retries
    except Exception as e:
        planner_sql = f"ERROR: {e}"
        detected_intent = "error"
        retries = 0

    time.sleep(0.5)  # rate limit between 3 generations

    # Judge all three
    def judge(sql):
        return judge_sql(engine, question, category, expected, sql, vst_summary)

    baseline_verdict = judge(baseline_sql)
    time.sleep(0.3)
    pm_verdict = judge(pm_sql)
    time.sleep(0.3)
    planner_verdict = judge(planner_sql)
    time.sleep(0.3)

    return {
        "id": q["id"],
        "intent": question,
        "category": category,
        "vst_family": q.get("vst_family"),
        "failure_type": q.get("failure_type"),
        "difficulty": q.get("difficulty"),
        "expected_behavior": expected,
        "detected_intent": detected_intent,
        "planner_retries": retries,
        "baseline": {
            "sql": baseline_sql,
            "verdict": baseline_verdict.get("verdict"),
            "reason": baseline_verdict.get("reason"),
            "semantic_issues": baseline_verdict.get("semantic_issues", []),
        },
        "prompt_mediated": {
            "sql": pm_sql,
            "verdict": pm_verdict.get("verdict"),
            "reason": pm_verdict.get("reason"),
            "semantic_issues": pm_verdict.get("semantic_issues", []),
        },
        "planner_enforced": {
            "sql": planner_sql,
            "verdict": planner_verdict.get("verdict"),
            "reason": planner_verdict.get("reason"),
            "semantic_issues": planner_verdict.get("semantic_issues", []),
        },
    }


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_summary(results: list[dict], domain: str) -> dict:
    systems = ["baseline", "prompt_mediated", "planner_enforced"]
    categories = sorted({r["category"] for r in results})

    def counts(sys_key):
        correct = sum(1 for r in results if r[sys_key]["verdict"] == "correct")
        partial = sum(1 for r in results if r[sys_key]["verdict"] == "partial")
        incorrect = sum(1 for r in results if r[sys_key]["verdict"] == "incorrect")
        total = len(results)
        return {
            "correct": correct,
            "partial": partial,
            "incorrect": incorrect,
            "correct_rate": round(correct / total, 3) if total else 0,
            "correct_or_partial_rate": round((correct + partial) / total, 3) if total else 0,
        }

    def category_counts(cat, sys_key):
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            return {}
        correct = sum(1 for r in rows if r[sys_key]["verdict"] == "correct")
        partial = sum(1 for r in rows if r[sys_key]["verdict"] == "partial")
        incorrect = sum(1 for r in rows if r[sys_key]["verdict"] == "incorrect")
        n = len(rows)
        return {
            "n": n,
            "correct": correct,
            "partial": partial,
            "incorrect": incorrect,
            "correct_rate": round(correct / n, 3),
            "correct_or_partial_rate": round((correct + partial) / n, 3),
        }

    def counts_for_rows(rows, sys_key):
        if not rows:
            return {}
        n = len(rows)
        correct = sum(1 for r in rows if r[sys_key]["verdict"] == "correct")
        partial = sum(1 for r in rows if r[sys_key]["verdict"] == "partial")
        return {
            "n": n,
            "correct_rate": round(correct / n, 3),
            "correct_or_partial_rate": round((correct + partial) / n, 3),
        }

    intent_breakdown = {}
    detected_intents = sorted({r.get("detected_intent", "unknown") for r in results})
    for det_intent in detected_intents:
        rows = [r for r in results if r.get("detected_intent") == det_intent]
        intent_breakdown[det_intent] = {
            sys: counts_for_rows(rows, sys) for sys in systems
        }

    return {
        f"{domain}_vsl_comparison": {
            "total_failure_cases": len(results),
            "overall": {sys: counts(sys) for sys in systems},
            "by_category": {
                cat: {sys: category_counts(cat, sys) for sys in systems}
                for cat in categories
            },
            "by_detected_intent": intent_breakdown,
            "notes": [
                "All three systems evaluated on exactly the same failure-category entries.",
                "baseline: schema-only prompt, no VST context.",
                "prompt_mediated: schema + all VST metadata as unstructured text hints.",
                "planner_enforced: intent-classified VST constraints + statistical thresholds "
                "+ rejection loop (max 2 retries).",
                "Judge: GPT-4o evaluates semantic correctness against expected_behavior.",
            ],
        }
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_benchmark(path: str) -> list[dict]:
    raw = Path(path).read_text()
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def run(domain: str, provider: str, model: str, out_dir: Path) -> list[dict]:
    cfg = DOMAIN_CONFIG[domain]

    benchmark_all = load_benchmark(cfg["benchmark"])
    # Include policy_grounding cases now that PolicyRegistry is wired in;
    # still exclude "none" (baseline-correct entries, not semantic failures)
    benchmark = [
        q for q in benchmark_all
        if q.get("category", "none") != "none"
    ]

    print(f"\n{'='*60}")
    print(f"VSL 3-Way Comparison — {domain}")
    print(f"Provider: {provider} / {model}")
    n_excluded = len(benchmark_all) - len(benchmark)
    n_policy = sum(1 for q in benchmark if q.get("category") == "policy_grounding")
    print(f"Failure cases: {len(benchmark)} (excluded {n_excluded} 'none'; {n_policy} policy_grounding)")
    print(f"{'='*60}")

    schema = load_schema(cfg["schema"])
    engine = NL2SQLEngine(provider=provider, model=model)
    registry = VSTRegistry.from_vsl_dir(cfg["vsl_dir"])
    policy_registry = PolicyRegistry.from_vsl_dir(cfg["vsl_dir"])
    planner = VSLPlanner()
    vst_summary = build_vst_summary(registry, "")

    if policy_registry:
        print(f"Policy registry: {policy_registry}")

    print(f"Registry: {registry}")
    print()

    results = []
    for i, q in enumerate(benchmark, 1):
        print(f"[{i:3}/{len(benchmark)}] {q['id']} ({q.get('category','?')}): {q['intent'][:55]}...")
        r = evaluate_question(
            q=q,
            engine=engine,
            schema=schema,
            registry=registry,
            planner=planner,
            vst_summary=vst_summary,
            policy_registry=policy_registry,
        )
        results.append(r)

        b = r["baseline"]["verdict"]
        pm = r["prompt_mediated"]["verdict"]
        pl = r["planner_enforced"]["verdict"]
        intent = r.get("detected_intent", "?")
        retries = r.get("planner_retries", 0)
        print(f"         intent={intent:20s} | base={b:9s} pm={pm:9s} planner={pl:9s}"
              + (f" [retry×{retries}]" if retries else ""))

    # Save detailed results
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    detail_path = out_dir / f"vsl_comparison_{domain}_{provider}_{model}_{ts}.json"
    detail_path.write_text(json.dumps({
        "run_at": datetime.utcnow().isoformat() + "Z",
        "provider": provider,
        "model": model,
        "domain": domain,
        "total": len(results),
        "results": results,
    }, indent=2))
    print(f"\nDetailed → {detail_path}")

    # Save per-domain summary
    summary = build_summary(results, domain)
    summary_path = out_dir / f"vsl_comparison_{domain}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary  → {summary_path}")

    _print_summary_table(summary, domain)

    return results


def _print_summary_table(summary: dict, domain: str) -> None:
    s = summary[f"{domain}_vsl_comparison"]
    ov = s["overall"]
    print(f"\n{'System':<20} {'Correct':>8} {'Partial':>8} {'Incorrect':>10} {'Correct%':>9} {'C+P%':>7}")
    print("-" * 65)
    for sys, vals in ov.items():
        print(
            f"{sys:<20} {vals['correct']:>8} {vals['partial']:>8} {vals['incorrect']:>10} "
            f"{vals['correct_rate']:>8.1%} {vals['correct_or_partial_rate']:>6.1%}"
        )

    print(f"\nBy category:")
    cats = s["by_category"]
    for cat, sys_vals in sorted(cats.items()):
        n = sys_vals["baseline"].get("n", 0)
        bl = sys_vals["baseline"].get("correct_or_partial_rate", 0)
        pm = sys_vals["prompt_mediated"].get("correct_or_partial_rate", 0)
        pl = sys_vals["planner_enforced"].get("correct_or_partial_rate", 0)
        print(f"  {cat:35s} n={n:2d}  base={bl:.0%}  pm={pm:.0%}  planner={pl:.0%}")


def build_combined_summary(all_results: dict[str, list[dict]]) -> dict:
    """Aggregate results across all domains into one combined summary."""
    combined = []
    for domain, results in all_results.items():
        for r in results:
            combined.append({**r, "_domain": domain})

    systems = ["baseline", "prompt_mediated", "planner_enforced"]

    def counts(sys_key, rows=None):
        rows = rows or combined
        n = len(rows)
        correct = sum(1 for r in rows if r[sys_key]["verdict"] == "correct")
        partial  = sum(1 for r in rows if r[sys_key]["verdict"] == "partial")
        incorrect = sum(1 for r in rows if r[sys_key]["verdict"] == "incorrect")
        return {
            "n": n,
            "correct": correct,
            "partial": partial,
            "incorrect": incorrect,
            "correct_rate": round(correct / n, 3) if n else 0,
            "correct_or_partial_rate": round((correct + partial) / n, 3) if n else 0,
        }

    categories = sorted({r["category"] for r in combined})
    by_cat = {}
    for cat in categories:
        rows = [r for r in combined if r["category"] == cat]
        by_cat[cat] = {sys: counts(sys, rows) for sys in systems}

    by_domain = {}
    for domain, results in all_results.items():
        by_domain[domain] = {
            "n": len(results),
            **{sys: counts(sys, results) for sys in systems},
        }

    return {
        "combined_vsl_comparison": {
            "domains": list(all_results.keys()),
            "total_failure_cases": len(combined),
            "overall": {sys: counts(sys) for sys in systems},
            "by_category": by_cat,
            "by_domain": by_domain,
            "notes": [
                "Non-policy, non-none semantic failure cases across all domains.",
                "baseline: schema-only, no VSL. prompt_mediated: full VST as text hints. "
                "planner_enforced: intent-classified constraints + rejection loop.",
            ],
        }
    }


def _print_combined_summary(summary: dict) -> None:
    s = summary["combined_vsl_comparison"]
    systems = ["baseline", "prompt_mediated", "planner_enforced"]
    print(f"\n{'='*70}")
    print(f"COMBINED SUMMARY ({s['total_failure_cases']} cases across {s['domains']})")
    print(f"{'='*70}")
    ov = s["overall"]
    print(f"\n{'System':<22} {'N':>4} {'Correct':>8} {'Partial':>8} {'Incorrect':>10} {'Correct%':>9} {'C+P%':>7}")
    print("-" * 72)
    for sys in systems:
        v = ov[sys]
        print(
            f"{sys:<22} {v['n']:>4} {v['correct']:>8} {v['partial']:>8} {v['incorrect']:>10} "
            f"{v['correct_rate']:>8.1%} {v['correct_or_partial_rate']:>6.1%}"
        )

    print(f"\nBy category (C+P% = correct-or-partial):")
    cats = s["by_category"]
    for cat, sv in sorted(cats.items()):
        n   = sv["baseline"]["n"]
        bl  = sv["baseline"]["correct_or_partial_rate"]
        pm  = sv["prompt_mediated"]["correct_or_partial_rate"]
        pl  = sv["planner_enforced"]["correct_or_partial_rate"]
        print(f"  {cat:35s} n={n:3d}  base={bl:.0%}  pm={pm:.0%}  planner={pl:.0%}")

    print(f"\nBy domain (C+P%):")
    for domain, dv in s["by_domain"].items():
        n  = dv["n"]
        bl = dv["baseline"]["correct_or_partial_rate"]
        pm = dv["prompt_mediated"]["correct_or_partial_rate"]
        pl = dv["planner_enforced"]["correct_or_partial_rate"]
        print(f"  {domain:20s} n={n:3d}  base={bl:.0%}  pm={pm:.0%}  planner={pl:.0%}")


def main() -> None:
    parser = argparse.ArgumentParser(description="VSL 3-Way Comparison Benchmark")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default=None)
    parser.add_argument("--domain", default="all",
                        choices=list(DOMAIN_CONFIG.keys()) + ["all"])
    parser.add_argument("--out-dir", default="benchmarks/nl2sql_results")
    args = parser.parse_args()

    defaults = {"openai": "gpt-4o", "gemini": "gemini-1.5-pro", "claude": "claude-sonnet-4-6"}
    model = args.model or defaults.get(args.provider, "gpt-4o")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    domains = list(DOMAIN_CONFIG.keys()) if args.domain == "all" else [args.domain]
    all_results: dict[str, list[dict]] = {}

    for domain in domains:
        results = run(domain=domain, provider=args.provider, model=model, out_dir=out_dir)
        all_results[domain] = results

    if len(domains) > 1:
        combined = build_combined_summary(all_results)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        comb_path = out_dir / f"vsl_comparison_combined_{args.provider}_{model}_{ts}.json"
        comb_path.write_text(json.dumps(combined, indent=2))
        print(f"\nCombined → {comb_path}")
        _print_combined_summary(combined)


if __name__ == "__main__":
    main()
