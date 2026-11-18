#!/usr/bin/env python3
"""
Regenerate the VSL vision-paper evaluation (Table 2) from the authoritative final labels.

Reads nl2sql_results/vsl_final_labels.csv (corrected verdicts; built from
the original sheets + the corrections in vsl_corrections_log.csv) and computes, for each of the four
conditions (data-dictionary D1, matched-prose D2, prompt-mediated PM, planner-enforced PE), the
fully / partially / unresolved counts and the per-category fully-resolved breakdown.

The reported counts are computed from the CSV; the paper's totals are checked as assertions, and the
PM-PE gap is computed from the data (not assumed). The script also validates the label file: exactly
124 unique case IDs, a known category for every case, and a valid verdict (correct / partial /
incorrect) present for every case under all four conditions. Any duplicate ID, unknown category, or
missing/invalid label aborts with a non-zero exit.

Dependencies: Python 3 standard library only. No model API or databases required.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from collections import defaultdict, Counter

LABELS = Path(__file__).resolve().parent / "nl2sql_results" / "vsl_final_labels.csv"
CATMAP = {"comparative_grounding": "Comparative", "process_misinterpretation": "Process",
          "quantitative_misinterpretation": "Quantitative", "role_confusion": "Role"}
CATS = ["Comparative", "Process", "Quantitative", "Role"]
CONDS = ["D1", "D2", "PM", "PE"]
LABEL = {"D1": "data-dictionary", "D2": "matched-prose", "PM": "prompt-mediated", "PE": "planner-enforced"}
VALID = {"correct", "partial", "incorrect"}
N_EXPECTED = 124
# paper's reported fully-resolved counts (checked as assertions, not used to compute anything)
EXPECT = {"D1": 17, "D2": 20, "PM": 35, "PE": 51}


def validate(rows: list[dict]) -> None:
    """Abort (SystemExit) on any structural problem in the label file."""
    errs = []
    if len(rows) != N_EXPECTED:
        errs.append(f"expected {N_EXPECTED} rows, found {len(rows)}")

    dups = [cid for cid, n in Counter(r["case_id"] for r in rows).items() if n > 1]
    if dups:
        errs.append(f"duplicate case IDs: {sorted(dups)}")

    for r in rows:
        cid = r.get("case_id", "<no id>")
        if r.get("category") not in CATMAP:
            errs.append(f"{cid}: unknown/missing category {r.get('category')!r}")
        for c in CONDS:
            v = (r.get(c) or "").strip()
            if v not in VALID:
                errs.append(f"{cid}: condition {c} has missing/invalid label {r.get(c)!r}")

    # every condition must label the full case set (no condition missing any case)
    ids = {r["case_id"] for r in rows}
    for c in CONDS:
        labeled = {r["case_id"] for r in rows if (r.get(c) or "").strip() in VALID}
        missing = ids - labeled
        if missing:
            errs.append(f"condition {c} missing labels for: {sorted(missing)}")

    if errs:
        print("FAIL: label file did not validate:")
        for e in errs:
            print(f"  - {e}")
        raise SystemExit(1)


def main() -> int:
    rows = list(csv.DictReader(open(LABELS)))
    validate(rows)

    full = {c: sum(r[c] == "correct" for r in rows) for c in CONDS}
    part = {c: sum(r[c] == "partial" for r in rows) for c in CONDS}
    unres = {c: sum(r[c] == "incorrect" for r in rows) for c in CONDS}

    ok = True
    print(f"{'Condition':16s} {'fully':>5} {'partial':>8} {'unres':>6}   full+partial")
    for c in CONDS:
        n = len(rows)
        assert full[c] + part[c] + unres[c] == n, f"{c}: counts do not sum to {n}"
        flag = "" if full[c] == EXPECT[c] else f"  !! expected {EXPECT[c]}"
        ok = ok and full[c] == EXPECT[c]
        print(f"{LABEL[c]:16s} {full[c]:>5} {part[c]:>8} {unres[c]:>6}   "
              f"{full[c]+part[c]} ({100*(full[c]+part[c])/n:.1f}%){flag}")

    print("\nFully-resolved by category (Comparative/Process/Quantitative/Role):")
    for c in CONDS:
        bycat = defaultdict(int)
        for r in rows:
            if r[c] == "correct":
                bycat[CATMAP[r["category"]]] += 1
        print(f"  {LABEL[c]:16s}: " + " / ".join(str(bycat[k]) for k in CATS) + f"  (total {sum(bycat.values())})")

    # ---- Full Table 2 (paper layout): Category | n | PM Fully/Partial | PE Fully/Partial ----
    def by_cat(cond: str, verdict: str) -> dict:
        d = defaultdict(int)
        for r in rows:
            if r[cond] == verdict:
                d[CATMAP[r["category"]]] += 1
        return d
    n_by = defaultdict(int)
    for r in rows:
        n_by[CATMAP[r["category"]]] += 1
    pmF, pmP = by_cat("PM", "correct"), by_cat("PM", "partial")
    peF, peP = by_cat("PE", "correct"), by_cat("PE", "partial")
    print("\nTable 2 (Category | n | PM-Fully | PM-Partial | PE-Fully | PE-Partial):")
    print(f"  {'Category':13s} {'n':>3} {'PM-F':>5} {'PM-P':>5} {'PE-F':>5} {'PE-P':>5}")
    for k in CATS:
        print(f"  {k:13s} {n_by[k]:>3} {pmF[k]:>5} {pmP[k]:>5} {peF[k]:>5} {peP[k]:>5}")
    print(f"  {'Total':13s} {sum(n_by.values()):>3} {sum(pmF.values()):>5} {sum(pmP.values()):>5} "
          f"{sum(peF.values()):>5} {sum(peP.values()):>5}")
    print(f"  Fully resolved of 124: data-dictionary {full['D1']}, matched prose {full['D2']}, "
          f"PM {full['PM']}, PE {full['PE']}")

    # gap computed from the data, then cross-checked against the paper's expected totals
    gap = full["PE"] - full["PM"]
    print(f"\nPM-PE fully-resolved gap (from data): {full['PE']} - {full['PM']} = {gap}")
    print("PASS: computed totals match the paper" if ok else "FAIL: see !! above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
