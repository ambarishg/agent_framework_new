import os
from dotenv import load_dotenv
from dotenv import dotenv_values

load_dotenv(override=True)
values_env = dotenv_values(".env")


AZURE_OPENAI_ENDPOINT = values_env["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_KEY = values_env["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_DEPLOYMENT_ID = values_env["AZURE_OPENAI_DEPLOYMENT_ID"]
