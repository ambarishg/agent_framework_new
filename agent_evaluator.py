import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from azure.ai.evaluation import (
    IntentResolutionEvaluator,
    ResponseCompletenessEvaluator,
    TaskAdherenceEvaluator,
    ToolCallAccuracyEvaluator,
)
from rich import print
from rich.table import Table


@dataclass(frozen=True)
class EvaluatorSpec:
    name: str
    result_key: str
    evaluator_cls: type
    requires_ground_truth: bool = False
    requires_tool_definitions: bool = False


class AgentEvaluator:
    """Reusable wrapper around Azure AI evaluation metrics for agent runs."""

    DEFAULT_EVALUATORS: dict[str, EvaluatorSpec] = {
        "IntentResolution": EvaluatorSpec(
            name="IntentResolution",
            result_key="intent_resolution",
            evaluator_cls=IntentResolutionEvaluator,
        ),
        "ResponseCompleteness": EvaluatorSpec(
            name="ResponseCompleteness",
            result_key="response_completeness",
            evaluator_cls=ResponseCompletenessEvaluator,
            requires_ground_truth=True,
        ),
        "TaskAdherence": EvaluatorSpec(
            name="TaskAdherence",
            result_key="task_adherence",
            evaluator_cls=TaskAdherenceEvaluator,
        ),
        "ToolCallAccuracy": EvaluatorSpec(
            name="ToolCallAccuracy",
            result_key="tool_call_accuracy",
            evaluator_cls=ToolCallAccuracyEvaluator,
            requires_tool_definitions=True,
        ),
    }

    def __init__(
        self,
        model_config: dict[str, Any],
        *,
        is_reasoning_model: bool = False,
        evaluator_specs: Mapping[str, EvaluatorSpec] | None = None,
    ) -> None:
        self.model_config = model_config
        self.is_reasoning_model = is_reasoning_model
        self.evaluator_specs = dict(evaluator_specs or self.DEFAULT_EVALUATORS)

    @staticmethod
    def _get_value(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, Mapping):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @classmethod
    def _get_role(cls, message: Any) -> str:
        role = cls._get_value(message, "role", "")
        if hasattr(role, "value"):
            return str(role.value)
        return str(role)

    @classmethod
    def _get_contents(cls, message: Any) -> list[Any]:
        contents = cls._get_value(message, "contents")
        if contents is not None:
            return list(contents)

        content = cls._get_value(message, "content")
        if content is None:
            return []
        if isinstance(content, list):
            return content
        if isinstance(content, str):
            return [{"type": "text", "text": content}]
        return [content]

    @staticmethod
    def _parse_json_if_needed(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    @classmethod
    def _normalize_tool_call(cls, content: Any) -> dict[str, Any]:
        nested_tool_call = cls._get_value(content, "tool_call", {})
        nested_function = cls._get_value(nested_tool_call, "function", {})

        call_id = (
            cls._get_value(content, "call_id")
            or cls._get_value(content, "tool_call_id")
            or cls._get_value(nested_tool_call, "id")
        )
        name = cls._get_value(content, "name") or cls._get_value(nested_function, "name")
        arguments = cls._get_value(content, "arguments", None)
        if arguments is None:
            arguments = cls._get_value(nested_function, "arguments")

        tool_call: dict[str, Any] = {
            "type": "tool_call",
            "name": name,
            "arguments": cls._parse_json_if_needed(arguments),
        }
        if call_id:
            tool_call["tool_call_id"] = call_id
        return tool_call

    @classmethod
    def _normalize_tool_result(cls, content: Any) -> tuple[str | None, Any]:
        call_id = cls._get_value(content, "call_id") or cls._get_value(content, "tool_call_id")
        result = cls._get_value(content, "result", None)
        if result is None:
            result = cls._get_value(content, "tool_result", None)
        if result is None:
            result = cls._get_value(content, "function_call_output", None)
        return call_id, result

    @classmethod
    def convert_to_evaluator_messages(cls, messages: Sequence[Any]) -> list[dict[str, Any]]:
        """Convert framework messages into the Azure AI evaluation schema."""
        evaluator_messages: list[dict[str, Any]] = []

        for message in messages:
            role = cls._get_role(message)
            content_items: list[dict[str, Any]] = []

            for content in cls._get_contents(message):
                content_type = cls._get_value(content, "type")

                if content_type in {"function_call", "tool_call", "openapi_call"}:
                    content_items.append(cls._normalize_tool_call(content))
                    continue

                if content_type in {"function_result", "tool_result", "function_call_output", "openapi_call_output"}:
                    call_id, result = cls._normalize_tool_result(content)
                    if call_id:
                        if content_items:
                            evaluator_messages.append({"role": role, "content": content_items})
                            content_items = []
                        evaluator_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": [{"type": "tool_result", "tool_result": result}],
                            }
                        )
                    else:
                        content_items.append({"type": "tool_result", "tool_result": result})
                    continue

                text = cls._get_value(content, "text")
                if content_type in {"text", "input_text", "output_text"} and text:
                    content_items.append({"type": "text", "text": text})

            if content_items:
                evaluator_messages.append({"role": role, "content": content_items})

        return evaluator_messages

    @classmethod
    def normalize_tool_definitions(cls, tools_or_definitions: Iterable[Any] | None) -> list[dict[str, Any]]:
        if tools_or_definitions is None:
            return []

        normalized: list[dict[str, Any]] = []
        for item in tools_or_definitions:
            if hasattr(item, "to_json_schema_spec"):
                normalized.append(item.to_json_schema_spec()["function"])
                continue

            if isinstance(item, Mapping) and "function" in item and isinstance(item["function"], Mapping):
                normalized.append(dict(item["function"]))
                continue

            if isinstance(item, Mapping):
                normalized.append(dict(item))
                continue

            raise TypeError(f"Unsupported tool definition type: {type(item).__name__}")
        return normalized

    @classmethod
    def build_query_messages(
        cls,
        query: str | Sequence[dict[str, Any]],
        *,
        system_message: str | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(query, str):
            messages: list[dict[str, Any]] = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            messages.append({"role": "user", "content": [{"type": "text", "text": query}]})
            return messages

        return [dict(message) for message in query]

    @classmethod
    def extract_response_messages(cls, response: Any) -> list[dict[str, Any]]:
        if isinstance(response, list):
            if response and isinstance(response[0], Mapping) and "role" in response[0]:
                if "contents" in response[0] or (
                    isinstance(response[0].get("content"), list)
                    and any(isinstance(item, Mapping) and "type" in item for item in response[0]["content"])
                ):
                    return cls.convert_to_evaluator_messages(response)
                return [dict(message) for message in response]
            return []

        messages = cls._get_value(response, "messages")
        if messages is not None:
            return cls.convert_to_evaluator_messages(messages)

        return []

    @classmethod
    def extract_response_text(cls, response: Any) -> str:
        if isinstance(response, str):
            return response

        text = cls._get_value(response, "text")
        if isinstance(text, str):
            return text

        messages = cls.extract_response_messages(response)
        text_parts: list[str] = []
        for message in messages:
            for content in message.get("content", []):
                if content.get("type") == "text" and content.get("text"):
                    text_parts.append(content["text"])
        return "\n".join(text_parts).strip()

    def _build_evaluator_kwargs(self) -> dict[str, Any]:
        return {
            "model_config": self.model_config,
            "is_reasoning_model": self.is_reasoning_model,
        }

    def _selected_specs(self, metrics: Sequence[str] | None) -> list[EvaluatorSpec]:
        if metrics is None:
            return list(self.evaluator_specs.values())

        selected: list[EvaluatorSpec] = []
        for name in metrics:
            if name not in self.evaluator_specs:
                raise KeyError(f"Unknown evaluator metric: {name}")
            selected.append(self.evaluator_specs[name])
        return selected

    @staticmethod
    def _skipped_result(reason: str) -> dict[str, Any]:
        return {
            "score": "N/A",
            "result": "skipped",
            "reason": reason,
            "raw": {"error_message": reason},
        }

    @staticmethod
    def _error_result(exc: Exception) -> dict[str, Any]:
        return {
            "score": "N/A",
            "result": "error",
            "reason": str(exc),
            "raw": {"error_message": str(exc)},
        }

    def evaluate(
        self,
        *,
        query: str | Sequence[dict[str, Any]],
        response: Any,
        ground_truth: str | None = None,
        tool_definitions: Iterable[Any] | None = None,
        system_message: str | None = None,
        metrics: Sequence[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        query_messages = self.build_query_messages(query, system_message=system_message)
        response_messages = self.extract_response_messages(response)
        response_text = self.extract_response_text(response)
        normalized_tool_definitions = self.normalize_tool_definitions(tool_definitions)

        results: dict[str, dict[str, Any]] = {}
        for spec in self._selected_specs(metrics):
            if spec.requires_ground_truth and not ground_truth:
                results[spec.name] = self._skipped_result("ground_truth is required for this evaluator.")
                continue

            if spec.requires_tool_definitions and not normalized_tool_definitions:
                results[spec.name] = self._skipped_result("tool_definitions are required for this evaluator.")
                continue

            evaluator = spec.evaluator_cls(**self._build_evaluator_kwargs())
            try:
                if spec.name == "ResponseCompleteness":
                    raw_result = evaluator(response=response_text, ground_truth=ground_truth)
                elif spec.name == "ToolCallAccuracy":
                    raw_result = evaluator(
                        query=query_messages,
                        response=response_messages,
                        tool_definitions=normalized_tool_definitions,
                    )
                else:
                    raw_result = evaluator(
                        query=query_messages,
                        response=response_messages,
                        tool_definitions=normalized_tool_definitions or None,
                    )

                results[spec.name] = {
                    "score": raw_result.get(spec.result_key, "N/A"),
                    "result": raw_result.get(f"{spec.result_key}_result", "N/A"),
                    "reason": raw_result.get(f"{spec.result_key}_reason", raw_result.get("error_message", "N/A")),
                    "raw": raw_result,
                }
            except Exception as exc:
                results[spec.name] = self._error_result(exc)

        return results

    def evaluate_run(
        self,
        *,
        query: str | Sequence[dict[str, Any]],
        agent_run: Any,
        ground_truth: str | None = None,
        tool_definitions: Iterable[Any] | None = None,
        system_message: str | None = None,
        metrics: Sequence[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        return self.evaluate(
            query=query,
            response=agent_run,
            ground_truth=ground_truth,
            tool_definitions=tool_definitions,
            system_message=system_message,
            metrics=metrics,
        )

    @staticmethod
    def display_results(results: Mapping[str, Mapping[str, Any]]) -> None:
        table = Table(title="Agent Evaluation Results", show_lines=True)
        table.add_column("Evaluator", style="cyan", width=28)
        table.add_column("Score", style="bold", justify="center", width=8)
        table.add_column("Result", justify="center", width=10)
        table.add_column("Reason", style="dim", width=70)

        for evaluator_name, result in results.items():
            score = str(result.get("score", "N/A"))
            outcome = str(result.get("result", "N/A"))
            reason = str(result.get("reason", "N/A"))

            if outcome == "pass":
                outcome = "[green]pass[/green]"
            elif outcome == "fail":
                outcome = "[red]fail[/red]"
            elif outcome == "skipped":
                outcome = "[yellow]skipped[/yellow]"
            elif outcome == "error":
                outcome = "[red]error[/red]"

            table.add_row(evaluator_name, score, outcome, reason)

        print()
        print(table)
