from config import *
from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
import logging
from openai import OpenAI

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

