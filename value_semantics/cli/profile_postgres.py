import argparse
import json
import os

from value_semantics import ValueSemanticsEngine
from value_semantics.connectors.postgres import PostgresConnector
from value_semantics.exporters.json_exporter import export_json
from value_semantics.inference.database_semantics import DatabaseSemanticsInferencer


def main():
    parser = argparse.ArgumentParser(
        description="Infer VSL metadata for all tables in a Postgres database"
    )

    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--schema", default="public")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--sample-size", type=int, default=1000)

    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    connector = PostgresConnector(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        schema=args.schema,
    )

    engine = ValueSemanticsEngine()
    table_results = {}

    index = {
        "database": args.database,
        "schema": args.schema,
        "tables": [],
        "database_vsl": os.path.join(args.out_dir, "database_vsl.json"),
    }

    for table_name in connector.list_tables():
        table_profile = connector.profile_table(
            table_name=table_name,
            sample_size=args.sample_size,
        )

        result = engine.infer_table(table_profile)
        table_results[table_name] = result

        out_path = os.path.join(args.out_dir, f"{table_name}_vsl.json")
        export_json(result, out_path)

        index["tables"].append(
            {
                "table": table_name,
                "path": out_path,
            }
        )

        print(f"Wrote {out_path}")

    database_semantics = DatabaseSemanticsInferencer().infer_database(
        table_results
    )

    with open(os.path.join(args.out_dir, "database_vsl.json"), "w") as f:
        json.dump(database_semantics, f, indent=2)

    print(f"Wrote {os.path.join(args.out_dir, 'database_vsl.json')}")

    with open(os.path.join(args.out_dir, "index.json"), "w") as f:
        json.dump(index, f, indent=2)


if __name__ == "__main__":
    main()