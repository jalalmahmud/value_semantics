import argparse
import json

from value_semantics.planning.sql_grounding import SQLGroundingPlanner


def main():
    parser = argparse.ArgumentParser(
        description="Ground a natural-language query using VSL metadata"
    )
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--question", required=True)

    args = parser.parse_args()

    with open(args.metadata, "r") as f:
        metadata = json.load(f)

    planner = SQLGroundingPlanner()
    result = planner.ground(
        question=args.question,
        vsl_metadata=metadata,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
