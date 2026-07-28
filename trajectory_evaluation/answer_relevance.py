"""Answer Relevance evaluator for LangSmith experiments."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from langchain_core.messages import BaseMessage, convert_to_messages
from openevals.llm import create_llm_as_judge
from openevals.prompts import ANSWER_RELEVANCE_PROMPT

from agent_system.models import build_chat_model


def _message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)


def _last_message_text(messages: Sequence[BaseMessage], message_type: str) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == message_type:
            text = _message_text(message).strip()
            if text:
                return text
    return ""


def _question_from_inputs(inputs: Mapping[str, Any]) -> str:
    question = inputs.get("question")
    if isinstance(question, str) and question.strip():
        return question.strip()

    raw_messages = inputs.get("messages", [])
    messages = list(convert_to_messages(raw_messages))
    question = _last_message_text(messages, "human")
    if not question:
        raise ValueError("No se encontró una consulta de usuario para evaluar.")
    return question


def _answer_from_outputs(outputs: Mapping[str, Any]) -> str:
    raw_messages = outputs.get("messages", [])
    messages = list(convert_to_messages(raw_messages))
    answer = _last_message_text(messages, "ai")
    if not answer:
        raise ValueError("No se encontró una respuesta final del asistente.")
    return answer


def build_answer_relevance_evaluator(
    *,
    judge_model: str | None = None,
) -> Callable[..., Any]:
    """Create the official OpenEvals Answer Relevance judge."""
    judge = create_llm_as_judge(
        **(
            {"model": judge_model}
            if judge_model
            else {"judge": build_chat_model()}
        ),
        prompt=ANSWER_RELEVANCE_PROMPT,
        feedback_key="answer_relevance",
    )

    def answer_relevance(
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        **_: Any,
    ) -> Any:
        return judge(
            inputs=_question_from_inputs(inputs),
            outputs=_answer_from_outputs(outputs),
        )

    answer_relevance.__name__ = "answer_relevance"
    return answer_relevance
