# value_semantics/exporters/json_exporter.py

import json


def export_json(result: dict, path: str):
    with open(path, "w") as f:
        json.dump(result, f, indent=2, default=str)