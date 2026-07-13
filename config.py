import os
from pathlib import Path
from dotenv import load_dotenv
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)
values_env = dotenv_values(ENV_PATH)


def _get_required_env(name: str) -> str:
    value = values_env.get(name) or os.getenv(name)
    if value is None:
        raise KeyError(f"Missing required environment variable: {name} (expected in {ENV_PATH})")
    return value


AZURE_OPENAI_ENDPOINT = _get_required_env("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = _get_required_env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_ID = _get_required_env("AZURE_OPENAI_DEPLOYMENT_ID")
MICROSOFT_FOUNDRY = _get_required_env("MICROSOFT_FOUNDRY")
