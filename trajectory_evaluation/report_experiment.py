"""Print an aggregate report for a completed LangSmith experiment."""

from __future__ import annotations

import argparse
from collections import defaultdict
from statistics import mean

from dotenv import load_dotenv
from langsmith import Client

load_dotenv()


def report(experiment: str) -> None:
    client = Client()
    runs = list(
        client.list_runs(
            project_name=experiment,
            is_root=True,
            select=["id", "reference_example_id", "error"],
        )
    )
    run_ids = [run.id for run in runs]
    scores: dict[str, list[float]] = defaultdict(list)
    if run_ids:
        for feedback in client.list_feedback(run_ids=run_ids):
            if feedback.score is not None:
                scores[feedback.key].append(float(feedback.score))

    print(f"Experimento: {experiment}")
    print(f"Casos ejecutados: {len(runs)}")
    print(f"Casos con error de ejecución: {sum(bool(run.error) for run in runs)}")
    for key in sorted(scores):
        values = scores[key]
        print(
            f"{key}: {mean(values):.3f} "
            f"({sum(value == 1 for value in values)}/{len(values)} con score 1)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resume los feedback scores de un experimento LangSmith."
    )
    parser.add_argument("--experiment", required=True)
    args = parser.parse_args()
    report(args.experiment)


if __name__ == "__main__":
    main()
