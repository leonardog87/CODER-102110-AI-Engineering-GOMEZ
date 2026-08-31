"""Create or update the canonical LangSmith evaluation dataset."""

from __future__ import annotations

import argparse
import os
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from langsmith import Client
from langsmith.utils import LangSmithNotFoundError

from trajectory_evaluation.trajectory_accuracy import DEFAULT_DATASET

load_dotenv()

EXAMPLES = [
    {"question": "¿Qué servicios ofrece la empresa?"},
    {"question": "¿Cuáles son los valores del negocio?"},
    {"question": "¿Cómo puedo contactar a soporte?"},
    {"question": "¿Cómo creo una cuenta?"},
    {"question": "Olvidé mi contraseña, ¿cómo recupero el acceso?"},
    {"question": "¿Qué procedimiento complejo debo seguir para esta gestión?"},
]


def ensure_dataset(dataset_name: str) -> tuple[str, int]:
    """Create the dataset and idempotently upsert the canonical examples."""
    if not os.getenv("LANGSMITH_API_KEY"):
        raise RuntimeError("Falta LANGSMITH_API_KEY en el entorno.")

    client = Client()
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except LangSmithNotFoundError:
        dataset = client.create_dataset(
            dataset_name,
            description=(
                "Casos genéricos para evaluar corrección, eficiencia y relevancia "
                "del agente único chatBot."
            ),
            metadata={"project": "chatBot", "version": 2},
        )

    existing_ids = {
        str(example.id)
        for example in client.list_examples(dataset_id=dataset.id)
    }
    synchronized = 0
    for inputs in EXAMPLES:
        stable_id = uuid5(
            NAMESPACE_URL,
            f"chatBot/{dataset_name}/{inputs['question']}",
        )
        metadata = {"source": "repository-canonical-dataset"}
        if str(stable_id) in existing_ids:
            client.update_example(
                stable_id,
                dataset_id=dataset.id,
                inputs=inputs,
                outputs={"messages": []},
                metadata=metadata,
            )
        else:
            client.create_example(
                example_id=stable_id,
                dataset_id=dataset.id,
                inputs=inputs,
                outputs={"messages": []},
                metadata=metadata,
            )
        synchronized += 1

    return str(dataset.id), synchronized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crea o actualiza el dataset canónico en LangSmith."
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv("LANGSMITH_TRAJECTORY_DATASET", DEFAULT_DATASET),
    )
    args = parser.parse_args()
    dataset_id, count = ensure_dataset(args.dataset)
    print(f"Dataset: {args.dataset}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Ejemplos sincronizados: {count}")


if __name__ == "__main__":
    main()
