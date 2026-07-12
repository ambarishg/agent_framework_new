# Agent Evaluator

This repository now includes a reusable [`AgentEvaluator`](./agent_evaluator.py) wrapper for the Azure AI Evaluation SDK. It is based on the flow in [`08-agent_evaluation.ipynb`](./08-agent_evaluation.ipynb) but removes the notebook-specific wiring so you can evaluate any `agent-framework` run programmatically.

## What It Does

`AgentEvaluator` can run these built-in Azure evaluators:

- `IntentResolution`
- `ResponseCompleteness`
- `TaskAdherence`
- `ToolCallAccuracy`

It also handles the message conversion required to turn `agent-framework` messages into the schema expected by Azure AI Evaluation.

## Requirements

Install dependencies from [`requirements.txt`](./requirements.txt):

```powershell
pip install -r requirements.txt
```

Set these environment variables in `.env`:

```env
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_ID=...
```

## Important Model Note

If your evaluation deployment is not a reasoning model, keep `is_reasoning_model=False`.

The Azure SDK can rewrite evaluator prompts to use large completion token limits when `is_reasoning_model=True`. In this repo that caused a `60000` token request, which exceeded the deployed model limit. Use `True` only when the evaluation deployment actually supports that reasoning-mode behavior.

## Basic Usage

Example with a small agent:

```python
from typing import Annotated

from pydantic import Field
from agent_framework import Agent, tool
from agent_evaluator import AgentEvaluator
from client import client, eval_model_config

query = (
    "Plan a 3-day trip from New York to Tokyo. "
    "My budget is $2000 total. I like hiking and museums."
)

@tool
def get_weather(
    city: Annotated[str, Field(description="City name")],
) -> dict:
    return {"city": city, "forecast": "Sunny"}

agent = Agent(
    client=client,
    instructions="You are a travel planning assistant.",
    tools=[get_weather],
)

response = await agent.run(query)
ground_truth = (
    "A complete itinerary with flights, hotels, activities, weather, "
    "and a cost breakdown that stays within budget."
)

evaluator = AgentEvaluator(
    model_config=eval_model_config,
    is_reasoning_model=False,
)

results = evaluator.evaluate_run(
    query=query,
    agent_run=response,
    system_message=agent.instructions,
    tool_definitions=agent.tools,
    ground_truth=ground_truth,
)

evaluator.display_results(results)
```

## API

### `AgentEvaluator(model_config, is_reasoning_model=False)`

- `model_config`: Azure AI Evaluation model configuration dictionary.
- `is_reasoning_model`: Set to `True` only for actual reasoning-model deployments.

### `evaluate_run(...)`

Use this when you have an `agent-framework` run object from `await agent.run(...)`.

```python
results = evaluator.evaluate_run(
    query=query,
    agent_run=response,
    system_message=agent.instructions,
    tool_definitions=tool_definitions,
    ground_truth=ground_truth,
)
```

Parameters:

- `query`: User query string or evaluator-style message list.
- `agent_run`: Run result object with `.messages` and optionally `.text`.
- `system_message`: Optional system or agent instruction text.
- `tool_definitions`: Tool list or normalized tool-definition dictionaries.
- `ground_truth`: Required for `ResponseCompleteness`.
- `metrics`: Optional subset such as `["IntentResolution", "TaskAdherence"]`.

### `evaluate(...)`

Use this when you want to evaluate any response-like object directly, not necessarily the raw run object.

```python
results = evaluator.evaluate(
    query=query,
    response=response,
    system_message=agent.instructions,
    tool_definitions=tool_definitions,
    ground_truth=ground_truth,
)
```

### `display_results(results)`

Renders a `rich` table in the terminal or notebook.

## Metric Input Rules

- `IntentResolution`: Needs `query` and `response`.
- `TaskAdherence`: Needs `query` and `response`.
- `ToolCallAccuracy`: Needs `query`, `response`, and `tool_definitions`.
- `ResponseCompleteness`: Needs `response` text and `ground_truth`.

If a required input is missing, `AgentEvaluator` marks that metric as `skipped` instead of failing the entire evaluation run.

## Using a Metric Subset

```python
results = evaluator.evaluate_run(
    query=query,
    agent_run=response,
    system_message=agent.instructions,
    tool_definitions=tool_definitions,
    metrics=["IntentResolution", "ToolCallAccuracy"],
)
```

## Tool Definition Inputs

You can pass either:

- Actual tool objects that implement `to_json_schema_spec()`
- Already-normalized tool definition dictionaries

Both of these work:

```python
results = evaluator.evaluate_run(
    query=query,
    agent_run=response,
    system_message=agent.instructions,
    tool_definitions=agent.tools,
)
```

```python
results = evaluator.evaluate_run(
    query=query,
    agent_run=response,
    system_message=agent.instructions,
    tool_definitions=[tool.to_json_schema_spec()["function"] for tool in agent.tools],
)
```

## Return Shape

Each evaluator result is returned under its metric name:

```python
{
    "IntentResolution": {
        "score": 4.0,
        "result": "pass",
        "reason": "...",
        "raw": {...}
    }
}
```

`raw` contains the unmodified Azure evaluator output for debugging or custom reporting.
