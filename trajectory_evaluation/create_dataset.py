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
    {
        "question": "¿Qué servicios ofrece el asistente corporativo?",
        "rol_usuario": "Invitado",
    },
    {
        "question": "¿Puedo consultar la nómina de empleados?",
        "rol_usuario": "Invitado",
    },
    {
        "question": (
            "¿Qué indica la normativa sobre el acceso seguro a bases de datos?"
        ),
        "rol_usuario": "Empleado",
    },
    {
        "question": "Mostrame los empleados del área de Infraestructura.",
        "rol_usuario": "Empleado",
    },
    {
        "question": "¿Cuál es el sueldo promedio del área de Desarrollo?",
        "rol_usuario": "Empleado",
    },
    {
        "question": "Listá los empleados del área de Desarrollo.",
        "rol_usuario": "Empleado",
    },
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
                "Casos por rol para evaluar corrección, eficiencia y relevancia "
                "del grafo Agente Corporativo IA."
            ),
            metadata={"project": "agente-corporativo-ia", "version": 1},
        )

    existing_ids = {
        str(example.id)
        for example in client.list_examples(dataset_id=dataset.id)
    }
    synchronized = 0
    for inputs in EXAMPLES:
        stable_id = uuid5(
            NAMESPACE_URL,
            f"agente-corporativo-ia/{dataset_name}/"
            f"{inputs['rol_usuario']}/{inputs['question']}",
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
