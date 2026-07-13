from config import *
from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatClient
from azure.ai.evaluation import (
    AzureOpenAIModelConfiguration,
    IntentResolutionEvaluator,
    OpenAIModelConfiguration,
    ResponseCompletenessEvaluator,
    TaskAdherenceEvaluator,
    ToolCallAccuracyEvaluator,
)
import logging
from openai import OpenAI
from agent_framework.orchestrations import MagenticBuilder, MagenticProgressLedger
from agent_framework import MCPStreamableHTTPTool
from agent_framework.orchestrations import HandoffBuilder
from agent_framework import AgentExecutorResponse, Executor, WorkflowBuilder, WorkflowContext, handler
from agent_framework.orchestrations import SequentialBuilder
from agent_framework import Message

endpoint = AZURE_OPENAI_ENDPOINT
deployment_name = AZURE_OPENAI_DEPLOYMENT_ID
api_key = AZURE_OPENAI_KEY

client = OpenAIChatClient(
        base_url=endpoint,
        api_key=api_key,
        model=deployment_name,
    )

logging.basicConfig(level=logging.WARNING, force=True, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

eval_model_config = OpenAIModelConfiguration(
        type="openai",
        base_url=endpoint,
        api_key=api_key,
        model=deployment_name,
    )




