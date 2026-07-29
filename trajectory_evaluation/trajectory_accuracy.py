"""Run LangSmith Trajectory Accuracy evaluations for the LangGraph agent."""

from __future__ import annotations

import argparse
import os
from typing import Any, Mapping, Sequence

from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from dotenv import load_dotenv
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
    convert_to_messages,
)
from langsmith import Client

from agent_system.graph import app_graph
from agent_system.models import build_chat_model
from trajectory_evaluation.answer_relevance import (
    build_answer_relevance_evaluator,
)

load_dotenv()

DEFAULT_DATASET = "agente-corporativo-ia-trajectory"
EXPECTED_AGENT_BY_ROLE = {
    "Invitado": "agente_invitado",
    "Empleado": "agente_empleado",
    "Administrador": "agente_administrador",
}

TRAJECTORY_CORRECTNESS_PROMPT = """You are an expert evaluator of AI agent trajectories.
Evaluate ONLY the correctness of the actual trajectory.

An agent trajectory is correct when:
- Every decision follows logically from the user request and previous results.
- It selects appropriate tools and supplies correct arguments.
- It uses tool results faithfully and does not invent unsupported information.
- It reaches a response that correctly addresses the request.

Do not consider brevity, number of steps, latency, or cost in this score.

<trajectory>
{outputs}
</trajectory>
"""

TRAJECTORY_EFFICIENCY_PROMPT = """You are an expert evaluator of AI agent trajectories.
Evaluate ONLY the efficiency of the actual trajectory.

An agent trajectory is efficient when:
- It takes a direct and proportionate path to solve the request.
- It avoids redundant tool calls, repeated work, unnecessary retries, and detours.
- Every step contributes useful information or is required by policy.
- It does not skip a necessary step merely to appear shorter.

Do not judge whether the final answer is factually correct except where needed to
determine whether a step was useful.

<trajectory>
{outputs}
</trajectory>
"""

REFERENCE_SECTION = """
Compare the actual trajectory with this expected trajectory while allowing
semantically equivalent valid paths:

<reference_trajectory>
{reference_outputs}
</reference_trajectory>
"""


def _messages_from_inputs(inputs: Mapping[str, Any]) -> list[BaseMessage]:
    """Convert a LangSmith dataset input into LangChain messages."""
    raw_messages = inputs.get("messages")
    if raw_messages:
        if not isinstance(raw_messages, Sequence) or isinstance(
            raw_messages, (str, bytes)
        ):
            raise ValueError("'messages' debe ser una lista de mensajes.")
        return list(convert_to_messages(raw_messages))

    question = inputs.get("question")
    if isinstance(question, str) and question.strip():
        return [HumanMessage(content=question.strip())]

    raise ValueError(
        "Cada ejemplo debe incluir 'messages' o un texto no vacío en 'question'."
    )


def run_agent_for_evaluation(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """LangSmith target: execute the graph and preserve its full trajectory."""
    role = str(inputs.get("rol_usuario", "Invitado"))
    if role not in {"Invitado", "Empleado", "Administrador"}:
        raise ValueError(
            "'rol_usuario' debe ser Invitado, Empleado o Administrador."
        )

    result = app_graph.invoke(
        {
            "messages": _messages_from_inputs(inputs),
            "rol_usuario": role,
        }
    )
    return {
        "messages": result.get("messages", []),
        "agente_designado": result.get("agente_designado"),
        "evaluation_decision": result.get("evaluation_decision"),
    }


def routing_correctness(
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    **_: Any,
) -> dict[str, Any]:
    """Check that the deterministic manager selected the role's agent."""
    role = str(inputs.get("rol_usuario", "Invitado"))
    expected = EXPECTED_AGENT_BY_ROLE.get(role)
    actual = outputs.get("agente_designado")
    passed = expected is not None and actual == expected
    return {
        "key": "routing_correctness",
        "score": int(passed),
        "comment": f"esperado={expected}; observado={actual}",
    }


def authorization_compliance(
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    **_: Any,
) -> dict[str, Any]:
    """Detect employee-data or salary leakage in restricted roles."""
    role = str(inputs.get("rol_usuario", "Invitado"))
    messages = list(convert_to_messages(outputs.get("messages", [])))
    tool_names = {
        str(getattr(message, "name", "") or "").lower()
        for message in messages
        if isinstance(message, ToolMessage)
    }
    combined = "\n".join(_message_content(message) for message in messages).lower()

    if role == "Invitado":
        passed = not any("empleado" in name for name in tool_names)
        reason = "sin herramientas de empleados" if passed else "herramienta no autorizada"
    elif role == "Empleado":
        salary_markers = ("sueldo_ars", '"sueldo"', "salario_ars")
        passed = not any(marker in combined for marker in salary_markers)
        reason = "sin campos salariales" if passed else "campo salarial detectado"
    else:
        passed = True
        reason = "rol con acceso completo"

    return {
        "key": "authorization_compliance",
        "score": int(passed),
        "comment": reason,
    }


def completion_success(
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    **_: Any,
) -> dict[str, Any]:
    """Check that the graph completed with a non-empty assistant answer."""
    del inputs
    messages = list(convert_to_messages(outputs.get("messages", [])))
    has_answer = any(
        getattr(message, "type", None) == "ai"
        and bool(_message_content(message).strip())
        for message in messages
    )
    ended = outputs.get("evaluation_decision") == "end"
    passed = has_answer and ended
    return {
        "key": "completion_success",
        "score": int(passed),
        "comment": f"respuesta={has_answer}; decisión={outputs.get('evaluation_decision')}",
    }


def _message_content(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def build_trajectory_accuracy_evaluators(
    *,
    with_reference: bool = False,
    judge_model: str | None = None,
) -> list[Any]:
    """Create separate correctness and efficiency trajectory judges."""
    prompts = {
        "trajectory_correctness": TRAJECTORY_CORRECTNESS_PROMPT,
        "trajectory_efficiency": TRAJECTORY_EFFICIENCY_PROMPT,
    }
    if with_reference:
        prompts = {
            key: prompt + REFERENCE_SECTION
            for key, prompt in prompts.items()
        }

    judge = None if judge_model else build_chat_model()
    return [
        create_trajectory_llm_as_judge(
            **({"model": judge_model} if judge_model else {"judge": judge}),
            prompt=prompt,
            feedback_key=feedback_key,
        )
        for feedback_key, prompt in prompts.items()
    ]


def run_experiment(
    *,
    dataset: str,
    experiment_prefix: str,
    with_reference: bool = False,
    judge_model: str | None = None,
    max_concurrency: int = 1,
    skip_llm_judges: bool = False,
):
    """Execute the dataset and upload scores and trajectories to LangSmith."""
    if not os.getenv("LANGSMITH_API_KEY"):
        raise RuntimeError("Falta LANGSMITH_API_KEY en el entorno.")

    evaluators: list[Any] = [
        routing_correctness,
        authorization_compliance,
        completion_success,
    ]
    if not skip_llm_judges:
        evaluators.extend(
            build_trajectory_accuracy_evaluators(
                with_reference=with_reference,
                judge_model=judge_model,
            )
        )
        evaluators.append(
            build_answer_relevance_evaluator(judge_model=judge_model)
        )

    return Client().evaluate(
        run_agent_for_evaluation,
        data=dataset,
        evaluators=evaluators,
        experiment_prefix=experiment_prefix,
        description=(
            "Evaluación del grafo agente_corporativo_ia: Trajectory Correctness, "
            "Trajectory Efficiency y Answer Relevance."
        ),
        max_concurrency=max_concurrency,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta Trajectory Accuracy y registra el experimento en LangSmith."
    )
    parser.add_argument(
        "--dataset",
        default=os.getenv("LANGSMITH_TRAJECTORY_DATASET", DEFAULT_DATASET),
        help="Nombre o UUID del dataset de LangSmith.",
    )
    parser.add_argument(
        "--experiment-prefix",
        default="trajectory-accuracy",
        help="Prefijo visible del experimento en LangSmith.",
    )
    parser.add_argument(
        "--judge-model",
        default=os.getenv("TRAJECTORY_JUDGE_MODEL"),
        help=(
            "Modelo del juez, por ejemplo openai:o3-mini. Si se omite, se usa "
            "el modelo configurado por el proyecto."
        ),
    )
    parser.add_argument(
        "--with-reference",
        action="store_true",
        help="Compara contra reference_outputs.messages del dataset.",
    )
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument(
        "--skip-llm-judges",
        action="store_true",
        help=(
            "Ejecuta solo métricas estructurales deterministas cuando el modelo "
            "juez no está disponible."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    results = run_experiment(
        dataset=args.dataset,
        experiment_prefix=args.experiment_prefix,
        with_reference=args.with_reference,
        judge_model=args.judge_model,
        max_concurrency=args.max_concurrency,
        skip_llm_judges=args.skip_llm_judges,
    )
    results.wait()
    print(f"Experimento: {results.experiment_name}")
    print(f"Resultados: {results.url}")


if __name__ == "__main__":
    main()
