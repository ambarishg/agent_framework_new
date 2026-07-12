# 08 Agent Evaluation Explained

This file explains the evaluators used in `08-agent_evaluation.ipynb` in a very simple and detailed way.

The notebook runs a travel-planning agent first, then it checks how well the agent performed using 4 evaluators from `azure.ai.evaluation`:

1. `IntentResolutionEvaluator`
2. `ResponseCompletenessEvaluator`
3. `TaskAdherenceEvaluator`
4. `ToolCallAccuracyEvaluator`

The main idea is simple:

- The user gives a travel request.
- The agent answers that request and may call tools.
- The notebook sends the query, the response, and sometimes the tool definitions or ground truth to evaluators.
- Each evaluator returns a result dictionary.
- The notebook picks out the important fields and shows them in a table.

## 1. What The Notebook Is Doing

The notebook has three important stages.

### Stage 1: Create the tools and agent

The notebook creates these tools:

- `get_weather`
- `search_flights`
- `search_hotels`
- `get_activities`
- `estimate_budget`

Then it creates:

- `tools`
- `tool_definitions`
- `AGENT_INSTRUCTIONS`
- `agent`

`tool_definitions` is important for evaluation because some evaluators need to know:

- what tools the agent had access to
- tool names
- tool parameters
- what the tool was supposed to do

### Stage 2: Run the agent

The notebook sends this travel request to the agent:

```python
query = (
    "Plan a 3-day trip from New York (JFK) to Tokyo, departing March 15 and returning March 18, "
    "2026. My budget is $2000 total. I like hiking and museums. Please search for flights, hotels "
    "under $150/night, check the weather, and suggest activities."
)
```

Then:

```python
response = await agent.run(query)
```

This gives two important things:

- `response.text`
  This is the final human-readable answer from the agent.
- `response.messages`
  This is the full conversation trace, including tool calls and tool results.

### Stage 3: Prepare evaluation inputs

The notebook creates:

```python
eval_query = [
    {"role": "system", "content": AGENT_INSTRUCTIONS},
    {"role": "user", "content": [{"type": "text", "text": query}]},
]
```

This is the query in the message format expected by the evaluators.

Then it creates:

```python
eval_response = convert_to_evaluator_messages(response.messages)
```

This is very important.

The agent framework stores tool calls in one format, but Azure AI evaluators expect another format. So the function `convert_to_evaluator_messages()` changes:

- `function_call` -> `tool_call`
- `function_result` -> `tool_result`

Without this conversion, the evaluators that inspect tool use may not understand the agent trace properly.

Then the notebook creates:

```python
ground_truth = (
    "A complete 3-day Tokyo trip itinerary from New York including: round-trip flight options with prices, "
    "hotel recommendations within nightly budget, hiking activities (e.g. Mt. Takao), museum visits "
    "(e.g. Tokyo National Museum, teamLab Borderless), weather forecast for the travel dates, "
    "a full cost breakdown showing total under $2000, and packing suggestions based on weather."
)
```

This is the expected answer description. It is not the exact final answer text. It is the reference that tells the completeness evaluator what should be present.

## 2. Common Output Structure

Each evaluator returns a dictionary. The notebook reads three main fields from it:

- `score`
- `result`
- `reason`

The notebook extracts them like this:

```python
evaluation_results[name] = {
    "score": result.get(key, "N/A"),
    "result": result.get(f"{key}_result", "N/A"),
    "reason": result.get(f"{key}_reason", result.get("error_message", "N/A")),
}
```

That means:

- `score` is the numeric or evaluator score for that metric
- `result` is usually something like `pass` or `fail`
- `reason` explains why the evaluator gave that result

For example, if the evaluator is `IntentResolution`, then the notebook looks for:

- `intent_resolution`
- `intent_resolution_result`
- `intent_resolution_reason`

## 3. Evaluator 1: IntentResolutionEvaluator

### Simple meaning

This evaluator checks:

"Did the agent understand the user’s request correctly and address the actual intent?"

It is not mainly checking whether the answer is long or pretty. It is checking whether the agent understood what the user wanted.

### In this notebook, the user wants:

- a 3-day Tokyo trip
- flight suggestions
- hotel suggestions under a budget
- weather
- activities based on hiking and museums
- a total plan within the budget

If the agent talks about something else, misses the main trip-planning goal, or misunderstands the request, this evaluator score will drop.

### Inputs used

The notebook calls it like this:

```python
intent_evaluator._to_async()(
    query=eval_query,
    response=eval_response,
    tool_definitions=tool_definitions
)
```

So it uses:

- `query=eval_query`
  The system instruction plus the user request
- `response=eval_response`
  The converted message trace
- `tool_definitions=tool_definitions`
  The list of available tools

### Why tool definitions are passed

Even though this evaluator is about intent, tool information helps it understand the environment in which the agent worked. It can see whether the agent used the available tools in a way that matches the user’s goal.

### What a good result looks like

A strong result usually means:

- the agent recognized this is a travel-planning task
- the agent answered the trip request directly
- the answer stays focused on flights, hotels, activities, weather, and budget

### What can make it fail

Common failure reasons:

- the agent misunderstood the destination or dates
- the agent ignored major parts of the request
- the agent answered too generically
- the agent drifted into unrelated content

### Output fields for this evaluator

This evaluator returns fields like:

- `intent_resolution`
- `intent_resolution_result`
- `intent_resolution_reason`

The notebook stores them as:

- `score`
- `result`
- `reason`

## 4. Evaluator 2: ResponseCompletenessEvaluator

### Simple meaning

This evaluator checks:

"How complete is the final answer compared to what should have been included?"

This is the evaluator that uses `ground_truth`.

### In this notebook, completeness means the final answer should contain:

- round-trip flight options with prices
- hotel recommendations within budget
- hiking suggestions
- museum suggestions
- weather forecast
- cost breakdown
- total staying under $2000
- packing suggestions based on weather

If some of these are missing, the completeness score may go down.

### Inputs used

The notebook calls it like this:

```python
completeness_evaluator._to_async()(
    response=response.text,
    ground_truth=ground_truth
)
```

So it uses:

- `response=response.text`
  Only the final text answer
- `ground_truth=ground_truth`
  The expected content description

### Important detail

This evaluator does not use the full tool-call trace in this notebook.

It compares:

- what the agent finally said
- what the notebook expected the answer to include

So this evaluator is more about final coverage than process.

### What a good result looks like

A strong result usually means the answer includes most or all of the expected trip details.

### What can make it fail

Common failure reasons:

- no weather details
- no hotel suggestions
- no activity suggestions
- no budget breakdown
- missing packing suggestions
- answer is too short or partial

### Output fields for this evaluator

This evaluator returns fields like:

- `response_completeness`
- `response_completeness_result`
- `response_completeness_reason`

## 5. Evaluator 3: TaskAdherenceEvaluator

### Simple meaning

This evaluator checks:

"Did the agent follow the task properly from start to finish?"

This is close to intent resolution, but not exactly the same.

- `IntentResolutionEvaluator` is more about understanding the request correctly.
- `TaskAdherenceEvaluator` is more about staying aligned with the task while answering it.

### In this notebook, task adherence means:

- follow the travel-planner role
- stay within the requested problem
- use the tools in a relevant way
- produce the kind of output the instructions asked for

The system instruction says:

- help users plan trips
- check weather
- find flights and hotels within budget
- suggest activities
- provide a complete itinerary
- keep the total within budget
- include weather for packing

So this evaluator checks whether the agent really followed those instructions in its behavior.

### Inputs used

The notebook calls it like this:

```python
adherence_evaluator._to_async()(
    query=eval_query,
    response=eval_response,
    tool_definitions=tool_definitions
)
```

So it uses:

- `query=eval_query`
- `response=eval_response`
- `tool_definitions=tool_definitions`

### Why this evaluator matters

An answer can understand the request but still not follow it carefully.

Example:

- the agent may understand that this is a Tokyo trip request
- but it may skip budget discipline
- or fail to include a proper itinerary
- or not use the available tools correctly enough

That can hurt task adherence.

### What a good result looks like

A strong result usually means:

- the response stayed on-task
- the agent followed the travel planning instructions
- the response structure matched the requested job

### What can make it fail

Common failure reasons:

- the agent ignored system instructions
- the answer did not stay inside the budget requirement
- the answer was incomplete in a way that breaks the task
- the agent produced content that does not match the requested deliverable

### Output fields for this evaluator

This evaluator returns fields like:

- `task_adherence`
- `task_adherence_result`
- `task_adherence_reason`

## 6. Evaluator 4: ToolCallAccuracyEvaluator

### Simple meaning

This evaluator checks:

"Did the agent call the right tools, with the right arguments, in the right way?"

This evaluator is very important when you want to evaluate agent behavior, not just final text.

### In this notebook, the available tools are:

- `get_weather`
- `search_flights`
- `search_hotels`
- `get_activities`
- `estimate_budget`

The user asked for:

- weather
- flights
- hotels under `$150/night`
- hiking and museum activities
- budget-aware planning

So a strong tool accuracy result usually means the agent:

- called the correct tools
- passed sensible arguments
- used tools relevant to the request

### Inputs used

The notebook calls it like this:

```python
tool_accuracy_evaluator._to_async()(
    query=eval_query,
    response=eval_response,
    tool_definitions=tool_definitions
)
```

So it uses:

- `query=eval_query`
- `response=eval_response`
- `tool_definitions=tool_definitions`

### Why `convert_to_evaluator_messages()` is critical here

This evaluator needs to inspect tool usage.

Your agent framework stores messages in its own format. Azure evaluator expects a schema like:

- text items
- `tool_call`
- `tool_result`

That is why the notebook converts:

- `function_call` -> `tool_call`
- `function_result` -> `tool_result`

If this conversion is wrong, `ToolCallAccuracyEvaluator` may give weak results or may not properly understand what the agent did.

### What this evaluator looks at

In simple terms, it checks things like:

- Was the correct tool chosen?
- Were the arguments sensible?
- Did the tool use match the user request?
- Did the agent avoid irrelevant or missing tool calls?

### What a good result looks like

Examples of good tool behavior:

- `search_flights` called with New York/JFK -> Tokyo and correct dates
- `search_hotels` called with Tokyo and a budget cap near `$150`
- `get_weather` called for Tokyo and the correct date range
- `get_activities` called with interests like hiking and museums
- `estimate_budget` called with the total budget and number of days

### What can make it fail

Common failure reasons:

- wrong tool selected
- tool not called when needed
- wrong dates
- wrong city
- wrong budget argument
- unnecessary tools used
- tool results ignored or misused

### Output fields for this evaluator

This evaluator returns fields like:

- `tool_call_accuracy`
- `tool_call_accuracy_result`
- `tool_call_accuracy_reason`

## 7. Why Different Evaluators Need Different Inputs

The notebook does not send the exact same inputs to every evaluator because each evaluator measures something different.

### IntentResolutionEvaluator

Needs:

- query
- response
- tool definitions

Because it checks whether the agent correctly understood and addressed the request.

### ResponseCompletenessEvaluator

Needs:

- final response text
- ground truth

Because it checks whether the final answer contains the expected information.

### TaskAdherenceEvaluator

Needs:

- query
- response
- tool definitions

Because it checks whether the agent stayed aligned with the task and instructions.

### ToolCallAccuracyEvaluator

Needs:

- query
- response
- tool definitions

Because it checks the tool usage behavior in detail.

## 8. Why `asyncio.gather()` Is Used

The notebook runs all evaluators together:

```python
intent_result, completeness_result, adherence_result, tool_accuracy_result = await asyncio.gather(
    intent_evaluator._to_async()(query=eval_query, response=eval_response, tool_definitions=tool_definitions),
    completeness_evaluator._to_async()(response=response.text, ground_truth=ground_truth),
    adherence_evaluator._to_async()(query=eval_query, response=eval_response, tool_definitions=tool_definitions),
    tool_accuracy_evaluator._to_async()(
        query=eval_query, response=eval_response, tool_definitions=tool_definitions
    ),
)
```

This means the notebook evaluates all 4 metrics concurrently instead of one after another.

Why this helps:

- faster execution
- cleaner notebook code
- all results come back together

## 9. How The Final Display Is Built

After each evaluator returns its dictionary, the notebook builds `evaluation_results`.

Example structure:

```python
{
    "IntentResolution": {
        "score": ...,
        "result": ...,
        "reason": ...
    },
    "ResponseCompleteness": {
        "score": ...,
        "result": ...,
        "reason": ...
    },
}
```

Then:

```python
display_evaluation_results(evaluation_results)
```

This prints a `rich` table with:

- Evaluator
- Score
- Result
- Reason

So the output you finally see is not the raw evaluator dictionary. It is a cleaned and formatted summary table.

## 10. Simple End-To-End Flow

Here is the full flow in plain language:

1. The notebook defines travel tools.
2. The notebook creates a travel-planning agent.
3. A travel request is sent to the agent.
4. The agent returns final text and message history.
5. The notebook converts message history into Azure evaluator format.
6. The notebook defines a `ground_truth` description.
7. The notebook runs 4 evaluators.
8. Each evaluator returns a score, result, and reason.
9. The notebook formats those results into a table.

## 11. Very Short Summary Of Each Evaluator

### `IntentResolutionEvaluator`

Checks whether the agent understood what the user actually wanted.

### `ResponseCompletenessEvaluator`

Checks whether the final answer contains all important expected information.

### `TaskAdherenceEvaluator`

Checks whether the agent stayed faithful to the task and system instructions.

### `ToolCallAccuracyEvaluator`

Checks whether the agent used the right tools correctly.

## 12. If You Want Better Evaluation Outputs

To get more meaningful outputs from these evaluators, these points matter a lot:

- Make `ground_truth` specific and realistic.
- Make sure `convert_to_evaluator_messages()` correctly maps every tool call and tool result.
- Pass complete `tool_definitions`.
- Keep system instructions clear.
- Make the user query specific enough to measure success and failure.

## 13. Most Important Practical Takeaway

If you remember only one thing, remember this:

- `IntentResolutionEvaluator` checks understanding.
- `ResponseCompletenessEvaluator` checks coverage.
- `TaskAdherenceEvaluator` checks whether the agent stayed on task.
- `ToolCallAccuracyEvaluator` checks whether tool usage was correct.

That is the whole evaluation logic of `08-agent_evaluation.ipynb`.
