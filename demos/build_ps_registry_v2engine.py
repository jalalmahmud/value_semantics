#!/usr/bin/env python3
"""
Build the public-safety VST registry with the value_semantics INFERENCE ENGINE
(ValueSemanticsEngine configured with the improved value-typing modules in value_type_v2.py), from
the raw crash CSV. This replaces the earlier standalone pandas builder: public safety is now produced
by the same engine as finance/HR, so all three evaluation registries are engine-generated.

The engine's value-typing modules correctly type a flat event table: coordinates (lat/long) as
spatial (non-additive), zip as a non-additive categorical code, crash_date/crash_time as event
time (bucketable), and the number_of_* columns as additive counts.

Usage:
  python3 demos/build_ps_registry_v2engine.py                       # -> demos/public_safety_vsl_rebuilt/
  python3 demos/build_ps_registry_v2engine.py --out-dir demos/public_safety_vsl   # rebuild in place
"""
from __future__ import annotations
import sys, json, argparse
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))         # for value_type_v2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # for value_semantics
from value_type_v2 import make_engine_v2
from value_semantics.profilers.dataframe import DataFrameProfiler
from value_semantics.inference.database_semantics import DatabaseSemanticsInferencer
from value_semantics.exporters.json_exporter import export_json

RAW_CSV = Path("demos/data/crashes_raw.csv")
RENAME = {"vehicle_type_code1": "vehicle_type_code_1", "vehicle_type_code2": "vehicle_type_code_2"}
SCHEMA_COLS = [
    "collision_id", "crash_date", "crash_time", "borough", "zip_code", "latitude", "longitude",
    "on_street_name", "cross_street_name", "number_of_persons_injured", "number_of_persons_killed",
    "number_of_pedestrians_injured", "number_of_pedestrians_killed", "number_of_cyclist_injured",
    "number_of_cyclist_killed", "number_of_motorist_injured", "number_of_motorist_killed",
    "contributing_factor_vehicle_1", "contributing_factor_vehicle_2", "contributing_factor_vehicle_3",
    "vehicle_type_code_1", "vehicle_type_code_2", "vehicle_type_code_3",
]


def build(out_dir: Path):
    raw = pd.read_csv(RAW_CSV, low_memory=False).rename(columns=RENAME)
    df = raw[[c for c in SCHEMA_COLS if c in raw.columns]].copy()
    for c in [x for x in SCHEMA_COLS if x.startswith("number_of_")]:
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ("latitude", "longitude"):
        if c in df: df[c] = pd.to_numeric(df[c], errors="coerce")
    df["collision_id"] = pd.to_numeric(df["collision_id"], errors="coerce")
    df["crash_date"] = pd.to_datetime(df["crash_date"], errors="coerce")
    df["zip_code"] = df["zip_code"].apply(lambda x: str(int(x)) if pd.notna(x) else None)

    eng = make_engine_v2()
    res = eng.infer_table(DataFrameProfiler().profile(df, "crashes"))

    out_dir.mkdir(parents=True, exist_ok=True)
    export_json(res, str(out_dir / "crashes_vsl.json"))
    (out_dir / "database_vsl.json").write_text(
        json.dumps(DatabaseSemanticsInferencer().infer_database({"crashes": res}), indent=2, default=str))
    (out_dir / "index.json").write_text(json.dumps({
        "database": "public_safety", "schema": "public",
        "tables": [{"table": "crashes", "path": str(out_dir / "crashes_vsl.json")}],
        "database_vsl": str(out_dir / "database_vsl.json")}, indent=2))
    print(f"public-safety registry (engine-built) -> {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="demos/public_safety_vsl_rebuilt",
                    help="output dir (default demos/public_safety_vsl_rebuilt, so the shipped registry "
                         "is NOT overwritten; pass demos/public_safety_vsl to rebuild in place)")
    build(Path(ap.parse_args().out_dir))
