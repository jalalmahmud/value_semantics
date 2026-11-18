# value_semantics/cli/main.py

import argparse
import pandas as pd

from value_semantics import ValueSemanticsEngine
from value_semantics.profilers.dataframe import DataFrameProfiler
from value_semantics.exporters.json_exporter import export_json


def main():
    parser = argparse.ArgumentParser(description="VSL Tool: infer value semantics from tables")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--out", required=True)

    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    table = DataFrameProfiler().profile(df, table_name=args.table)

    result = ValueSemanticsEngine().infer_table(table)
    export_json(result, args.out)

    print(f"Wrote VSL metadata to {args.out}")


if __name__ == "__main__":
    main()